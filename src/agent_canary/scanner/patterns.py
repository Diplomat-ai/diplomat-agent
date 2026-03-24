"""Catalogue of side-effect and guard patterns for AST scanning.

Patterns are data, not logic. Each entry describes what to look for in Python AST
and how to categorize it. Extend this file to add new patterns.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Side-effect patterns
# ---------------------------------------------------------------------------
# Each entry is a dict with:
#   category  : str   — the SideEffect category
#   risk      : int   — 1 (low) to 3 (high), used for prioritization
#   match     : dict  — what to match in the AST call node
#     "func_contains"   : list[str] — the function/attribute name must contain one of these strings
#     "attr_contains"   : list[str] — the attribute name (last part) must contain one of these
#     "obj_contains"    : list[str] — the object/receiver name must contain one of these
#     "sql_contains"    : list[str] — relevant for cursor.execute(): the first arg string must contain one of these
#     "name_contains"   : list[str] — for standalone function calls: the function name must contain one of these

# ---------------------------------------------------------------------------
# Orchestrator decorators — functions that may be auto-retried
# ---------------------------------------------------------------------------
ORCHESTRATOR_DECORATORS: list[str] = [
    "activity.defn",        # Temporal
    "activity_defn",        # Temporal (local alias)
    "celery_app.task",      # Celery
    "shared_task",          # Celery
    "app.task",             # Celery
    "dramatiq.actor",       # Dramatiq
    "job",                  # RQ, Huey
    "task",                 # Airflow, Prefect
]

SIDE_EFFECT_PATTERNS: list[dict] = [
    # -----------------------------------------------------------------------
    # Payment / Financial
    # -----------------------------------------------------------------------
    {
        "category": "payment",
        "risk": 3,
        "match": {
            "obj_contains": ["stripe"],
            "attr_contains": [
                "create", "capture", "refund", "charge", "transfer",
                "payout", "payment", "subscription",
            ],
        },
    },
    {
        "category": "payment",
        "risk": 3,
        "match": {
            "func_contains": [
                "stripe.Refund.create", "stripe.Charge.create",
                "stripe.PaymentIntent.create", "stripe.Transfer.create",
                "stripe.Payout.create", "stripe.Customer.create",
                "stripe.Subscription.create",
            ],
        },
    },
    {
        "category": "payment",
        "risk": 3,
        "match": {
            "obj_contains": ["paypal", "braintree", "adyen", "square", "mollie"],
            "attr_contains": ["payment", "charge", "capture", "refund", "sale", "execute"],
        },
    },
    {
        "category": "payment",
        "risk": 3,
        "match": {
            "name_contains": ["refund", "charge", "payout", "payment_create", "transfer_funds"],
        },
    },

    # -----------------------------------------------------------------------
    # Database Write
    # -----------------------------------------------------------------------
    {
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["session", "db", "conn", "connection"],
            "attr_contains": ["add", "commit", "flush", "merge"],
        },
    },
    {
        # session.execute() / db.execute() — write unless first arg is select() or SELECT text
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["session", "db", "conn", "connection"],
            "attr_exact": ["execute", "executemany"],
            "first_arg_excludes": ["select"],
            "sql_excludes": ["SELECT"],
        },
    },
    {
        # ORM-style: Model.objects.create(), queryset.update(), obj.save()
        # Require an ORM-context object to avoid matching payment SDK .create() calls
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["objects", "queryset", "model", "manager", "repo", "repository",
                              "store", "dao", "entity"],
            "attr_contains": ["save", "insert", "create", "update", "upsert", "bulk_create",
                              "bulk_update", "get_or_create", "update_or_create"],
        },
    },
    {
        # Generic .save() on any object (likely ORM model instance)
        "category": "database_write",
        "risk": 2,
        "match": {
            "attr_contains": ["save"],
        },
    },
    {
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["cursor"],
            "attr_contains": ["execute", "executemany"],
            "sql_contains": ["INSERT", "UPDATE", "REPLACE"],
        },
    },
    {
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["collection", "mongo", "db"],
            "attr_contains": ["insert", "insert_one", "insert_many", "update", "update_one",
                              "update_many", "replace_one", "find_one_and_update",
                              "find_one_and_replace"],
        },
    },
    {
        # Isolated .commit() — persists mutations made elsewhere (ORM pattern)
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["db", "session", "connection", "conn", "tx", "transaction"],
            "attr_contains": ["commit"],
        },
    },

    # -----------------------------------------------------------------------
    # Database Delete
    # -----------------------------------------------------------------------
    {
        "category": "database_delete",
        "risk": 3,
        "match": {
            "obj_contains": ["session", "db", "conn"],
            "attr_contains": ["delete"],
        },
    },
    {
        # Repository/DAO delete: repo.delete(), repository.destroy(), etc.
        "category": "database_delete",
        "risk": 3,
        "match": {
            "obj_contains": ["repo", "repository", "dao", "store", "manager"],
            "attr_contains": ["delete", "destroy", "remove", "purge"],
        },
    },
    {
        # Generic delete/destroy/purge — longer verbs less likely to be substrings in helper names.
        # "drop" and "truncate" intentionally excluded here — covered by context-specific patterns below.
        "category": "database_delete",
        "risk": 3,
        "match": {
            "attr_contains": ["delete", "destroy", "purge"],
        },
    },
    {
        "category": "database_delete",
        "risk": 3,
        "match": {
            "obj_contains": ["cursor"],
            "attr_contains": ["execute", "executemany"],
            "sql_contains": ["DELETE", "DROP", "TRUNCATE"],
        },
    },
    {
        "category": "database_delete",
        "risk": 3,
        "match": {
            "obj_contains": ["collection", "mongo", "db"],
            "attr_contains": ["delete_one", "delete_many", "drop", "remove"],
        },
    },
    {
        # SQLAlchemy / Alembic schema-level drop: metadata.drop_all(), engine.drop_all()
        "category": "database_delete",
        "risk": 3,
        "match": {
            "obj_contains": ["metadata", "engine", "schema", "base"],
            "attr_contains": ["drop_all", "drop"],
        },
    },

    # -----------------------------------------------------------------------
    # HTTP Write (external API calls)
    # -----------------------------------------------------------------------
    {
        "category": "http_write",
        "risk": 2,
        "match": {
            "obj_contains": ["requests", "httpx", "aiohttp", "session", "client", "http"],
            "attr_contains": ["post", "put", "patch", "delete"],
        },
    },
    {
        "category": "http_write",
        "risk": 2,
        "match": {
            "name_contains": ["requests.post", "requests.put", "requests.patch", "requests.delete",
                              "httpx.post", "httpx.put", "httpx.patch", "httpx.delete"],
        },
    },

    # -----------------------------------------------------------------------
    # Email / Messaging
    # -----------------------------------------------------------------------
    {
        "category": "email",
        "risk": 2,
        "match": {
            "name_contains": ["send_mail", "send_email", "sendmail", "send_message"],
        },
    },
    {
        "category": "email",
        "risk": 2,
        "match": {
            "obj_contains": ["smtp", "mailer", "mail", "email", "ses_client", "ses_service"],
            "attr_contains": ["send", "sendmail", "send_message", "send_email"],
        },
    },
    {
        # Bare "ses" variable (AWS SES client) — exact match to avoid cdp_session etc.
        "category": "email",
        "risk": 2,
        "match": {
            "obj_exact": ["ses"],
            "attr_contains": ["send", "send_email", "send_raw_email", "send_templated_email"],
        },
    },
    {
        "category": "email",
        "risk": 2,
        "match": {
            "obj_contains": ["slack", "slack_client", "slack_sdk"],
            "attr_contains": ["post", "chat_postMessage", "post_message", "send"],
        },
    },
    {
        "category": "email",
        "risk": 2,
        "match": {
            "obj_contains": ["twilio", "sms", "vonage", "nexmo"],
            "attr_contains": ["create", "send", "messages"],
        },
    },
    {
        "category": "email",
        "risk": 2,
        "match": {
            "obj_contains": ["telegram_bot", "discord_bot", "telegram", "discord"],
            "attr_contains": ["send_message", "send", "post_message"],
        },
    },
    {
        "category": "email",
        "risk": 2,
        "match": {
            "name_contains": ["notify", "send_notification", "send_sms", "send_slack"],
        },
    },

    # -----------------------------------------------------------------------
    # Publish / CMS / Cloud Storage
    # -----------------------------------------------------------------------
    {
        "category": "publish",
        "risk": 2,
        "match": {
            "attr_exact": ["publish"],
        },
    },
    {
        "category": "publish",
        "risk": 2,
        "match": {
            "name_contains": ["deploy", "upload", "push_content"],
        },
    },
    {
        "category": "publish",
        "risk": 2,
        "match": {
            "obj_contains": ["s3", "blob", "storage", "gcs", "azure"],
            "attr_contains": ["put", "put_object", "upload", "upload_file", "upload_fileobj",
                              "upload_blob", "from_string"],
        },
    },
    {
        "category": "publish",
        "risk": 2,
        "match": {
            "obj_contains": ["cms", "wordpress", "contentful", "strapi", "ghost"],
            "attr_contains": ["create", "update", "publish", "post"],
        },
    },

    # -----------------------------------------------------------------------
    # File System Destructive
    # -----------------------------------------------------------------------
    {
        "category": "file_delete",
        "risk": 2,
        "match": {
            "name_contains": ["os.remove", "os.unlink", "shutil.rmtree", "shutil.move"],
        },
    },
    {
        "category": "file_delete",
        "risk": 2,
        "match": {
            "obj_contains": ["os", "shutil"],
            "attr_contains": ["remove", "unlink", "rmtree", "rmdir"],
        },
    },
    {
        "category": "file_delete",
        "risk": 2,
        "match": {
            "obj_contains": ["path", "pathlib"],
            "attr_contains": ["unlink", "rmdir"],
        },
    },

    # -----------------------------------------------------------------------
    # Destructive (irreversible operations that don't fit other categories)
    # -----------------------------------------------------------------------
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "name_contains": ["subprocess.run", "subprocess.call", "subprocess.Popen",
                              "os.system", "os.exec", "os.popen"],
        },
    },
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "obj_contains": ["subprocess"],
            "attr_contains": ["run", "call", "Popen", "check_call", "check_output"],
        },
    },
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "name_contains": ["shutdown", "terminate", "kill_process", "reboot",
                              "format_disk", "wipe", "reset_factory"],
        },
    },
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "obj_contains": ["docker", "k8s", "kubernetes"],
            "attr_contains": ["remove", "kill", "stop", "delete", "destroy", "scale"],
        },
    },
    {
        # Dynamic code execution — exec() / eval() / __import__() builtins
        # attr_exact avoids matching cursor.execute(), ast.literal_eval(), etc.
        "category": "destructive",
        "risk": 3,
        "match": {
            "attr_exact": ["exec", "eval", "__import__"],
        },
    },
    {
        # Dynamic module loading via importlib — loads and runs arbitrary code
        "category": "destructive",
        "risk": 3,
        "match": {
            "obj_exact": ["importlib"],
            "attr_exact": ["import_module"],
        },
    },

    # -----------------------------------------------------------------------
    # Agent / LLM Invocation
    # -----------------------------------------------------------------------
    {
        # .invoke() / .ainvoke() on graph, chain, pipeline, agent, workflow, runnable
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "obj_contains": ["graph", "chain", "pipeline", "agent", "workflow", "runnable"],
            "attr_exact": ["invoke", "ainvoke"],
        },
    },
    {
        # .run() on graph, chain, pipeline, agent, workflow
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "obj_contains": ["graph", "chain", "pipeline", "agent", "workflow"],
            "attr_exact": ["run", "arun"],
        },
    },
    {
        # .analyze() / .execute() / .process() on agent-like objects
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "obj_contains": ["agent", "analyzer", "executor", "processor",
                              "scraper", "brief"],
            "attr_exact": ["analyze", "execute", "process"],
        },
    },

    # -----------------------------------------------------------------------
    # LLM Call — direct SDK calls and custom wrappers
    # -----------------------------------------------------------------------
    {
        # OpenAI: chat.completions.create()
        "category": "llm_call",
        "risk": 2,
        "match": {
            "func_contains": ["chat.completions.create", "completions.create"],
        },
    },
    {
        # Anthropic: messages.create()
        "category": "llm_call",
        "risk": 2,
        "match": {
            "obj_contains": ["anthropic", "messages"],
            "attr_exact": ["create"],
        },
    },
    {
        # LiteLLM: litellm.completion() / litellm.acompletion()
        "category": "llm_call",
        "risk": 2,
        "match": {
            "obj_exact": ["litellm"],
            "attr_contains": ["completion", "acompletion"],
        },
    },
    {
        # Custom LLM wrappers — function names containing action+llm combos
        "category": "llm_call",
        "risk": 2,
        "match": {
            "name_contains": [
                "llm_api", "llm_handler", "llm_call",
                "call_llm", "get_llm_response", "invoke_llm",
            ],
        },
    },
    {
        # .invoke() / .ainvoke() on llm or model objects
        "category": "llm_call",
        "risk": 2,
        "match": {
            "obj_contains": ["llm", "model"],
            "attr_exact": ["invoke", "ainvoke"],
        },
    },
]

# ---------------------------------------------------------------------------
# Read-only patterns (these alone → LOW_RISK, no guards needed)
# ---------------------------------------------------------------------------
READ_ONLY_PATTERNS: list[dict] = [
    {
        "match": {
            "obj_contains": ["requests", "httpx", "aiohttp", "session", "client"],
            "attr_contains": ["get", "head", "options"],
        },
    },
    {
        "match": {
            "name_contains": ["requests.get", "httpx.get"],
        },
    },
    {
        "match": {
            "obj_contains": ["cursor"],
            "attr_contains": ["execute", "fetchone", "fetchall", "fetchmany"],
            "sql_contains": ["SELECT"],
        },
    },
    {
        "match": {
            "attr_contains": ["get", "filter", "all", "first", "last", "count",
                              "exists", "values", "values_list", "find", "find_one"],
        },
    },
]

# ---------------------------------------------------------------------------
# Guard patterns
# ---------------------------------------------------------------------------
# Each entry describes a guard type to detect.
# "coverage" is "full" or "partial".

GUARD_PATTERNS: list[dict] = [
    # --- Input validation (Pydantic full) ---
    {
        "type": "input_validation",
        "coverage": "full",
        "match": {
            "func_contains": ["Field"],
            "kwarg_contains": ["le", "ge", "lt", "gt", "max_length", "min_length",
                               "pattern", "min_items", "max_items"],
        },
    },
    # --- Input validation (Pydantic decorators) ---
    {
        "type": "input_validation",
        "coverage": "full",
        "match": {
            "decorator_contains": ["validator", "field_validator"],
        },
    },
    # --- Input validation (manual if checks, partial) ---
    {
        "type": "input_validation",
        "coverage": "partial",
        "match": {
            "compare_contains": ["amount", "price", "value", "count", "limit",
                                 "quantity", "total", "max", "min"],
        },
    },
    # --- Rate limit ---
    {
        "type": "rate_limit",
        "coverage": "full",
        "match": {
            "decorator_contains": ["rate_limit", "ratelimit", "throttle", "limiter", "limit"],
        },
    },
    {
        "type": "rate_limit",
        "coverage": "full",
        "match": {
            "import_contains": ["ratelimit", "limits", "slowapi", "fastapi_limiter", "throttle"],
        },
    },
    # --- Auth check ---
    {
        "type": "auth_check",
        "coverage": "full",
        "match": {
            "decorator_contains": ["auth", "login_required", "permission_required",
                                   "requires", "has_permission", "authenticated"],
        },
    },
    {
        "type": "auth_check",
        "coverage": "partial",
        "match": {
            "name_contains": ["current_user", "get_current_user", "request.user",
                              "verify_token", "check_permission", "is_authenticated"],
        },
    },
    # --- Approval / confirmation ---
    {
        "type": "approval_step",
        "coverage": "full",
        "match": {
            "name_contains": ["approve", "confirm", "review", "require_approval",
                              "pending_approval", "awaiting_approval"],
        },
    },
    {
        "type": "approval_step",
        "coverage": "partial",
        "match": {
            "name_contains": ["confirm", "approval"],
        },
    },
    # --- Idempotency ---
    {
        "type": "idempotency_key",
        "coverage": "full",
        "match": {
            "name_contains": ["idempotency_key", "idempotency", "dedup", "get_or_create",
                              "upsert", "ON CONFLICT", "unique_constraint"],
        },
    },
    # --- Retry bound ---
    {
        "type": "retry_bound",
        "coverage": "full",
        "match": {
            "kwarg_contains": ["max_retries", "maximum_attempts", "max_tries", "max_attempts"],
        },
    },
    {
        "type": "retry_bound",
        "coverage": "full",
        "match": {
            "decorator_contains": ["retry", "backoff"],
        },
    },
    {
        "type": "retry_bound",
        "coverage": "full",
        "match": {
            "func_contains": ["stop_after_attempt", "max_tries"],
        },
    },
    # --- Input validation (manual assertions) ---
    {
        "type": "input_validation",
        "coverage": "partial",
        "match": {
            "name_contains": ["assert", "raise ValueError", "raise TypeError",
                              "raise ValidationError"],
        },
    },
    # --- Rate limit (manual / in-function) ---
    {
        "type": "rate_limit",
        "coverage": "partial",
        "match": {
            "name_contains": ["check_rate_limit", "is_rate_limited", "rate_limit_check",
                              "throttle_check"],
        },
    },
]

# Categories that are never considered harmful (read-only operations)
READ_CATEGORIES: frozenset[str] = frozenset({"read"})

# Directories to exclude from scanning
EXCLUDED_DIRS: frozenset[str] = frozenset({
    "venv", ".venv", "env", "__pycache__", ".git", "node_modules",
    "migrations", "alembic", ".tox", ".mypy_cache", ".ruff_cache",
    "dist", "build", "site-packages", ".pytest_cache",
    "tests", "test", "testing", "fixtures",
    "examples", "example", "benchmarks", "benchmark",
    "evals", "eval", "demos", "demo",
    "docs", "doc", "scripts",
})

# File patterns to exclude from scanning
EXCLUDED_FILE_PATTERNS: tuple[str, ...] = (
    "test_",
    "_test.py",
    "conftest.py",
)
