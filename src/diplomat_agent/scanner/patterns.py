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

# ---------------------------------------------------------------------------
# MCP server detection patterns
# ---------------------------------------------------------------------------
# Gate: these imports signal that a module is an MCP server. MCP detection is
# ONLY enabled when at least one of these is present — prevents false positives
# from random @x.tool decorators that happen to exist outside an MCP context.
MCP_SERVER_IMPORTS: list[str] = [
    "mcp.server.fastmcp",   # Official SDK (FastMCP 1.0 integrated)
    "fastmcp",              # FastMCP v2 standalone (jlowin / PrefectHQ)
    "mcp.server",           # Low-level API (Server + call_tool)
]

# @<instance>.tool — the instance name varies (mcp / app / server / etc.).
# Matched by attribute name only; gated by MCP_SERVER_IMPORTS to prevent FP.
# NOTE: bare @tool (from fastmcp import tool) is intentionally NOT matched
# in v1 — the attribute-based matching covers >95% of real-world cases with
# a lower false-positive risk than matching bare @tool.
MCP_TOOL_DECORATOR_ATTRS: list[str] = ["tool"]

# Read-only by MCP spec design — excluded from scan.
MCP_RESOURCE_DECORATOR_ATTRS: list[str] = ["resource", "prompt"]

# Low-level single-dispatcher pattern: @server.call_tool()
# Per-tool resolution is not supported in v1. A file-level stderr warning
# is emitted when this decorator is detected in an MCP module.
MCP_DISPATCH_DECORATOR_ATTRS: list[str] = ["call_tool"]

# FIX 3 — cross-module MCP gate: instance names commonly imported from a
# shared module (e.g. `from .server import mcp`). When a file imports one of
# these names via ImportFrom AND uses @<name>.tool(), it is treated as an MCP
# module even if the originating module is not in MCP_SERVER_IMPORTS.
MCP_INSTANCE_NAMES: frozenset[str] = frozenset(["mcp", "server", "app"])

# ---------------------------------------------------------------------------
# MCP client detection patterns (GATE 4)
# ---------------------------------------------------------------------------
# Imports that identify a module as an MCP *client* (consumer of an MCP server,
# not a server itself).
# Gate: module_is_mcp_client = bool(module_imports & MCP_CLIENT_IMPORTS) and not module_is_mcp
MCP_CLIENT_IMPORTS: frozenset[str] = frozenset({
    "mcp",
    "mcp.client",
    "mcp.client.streamable_http",
    "mcp.client.stdio",
    "mcp.client.sse",
})

# Session-like receiver names for MCP client call_tool call-site detection.
# A Call node with attr="call_tool" on one of these receivers inside a function
# body (NOT a decorator) marks that function as exposure="mcp_client" / OPAQUE.
MCP_CLIENT_SESSION_NAMES: frozenset[str] = frozenset({"session", "client", "_session"})

# FIX B v1 (v0.5.0) — programmatic tool registration call attributes.
# Detects mcp.add_tool(fn) / server.add_tool(fn) / app.tool(fn) (call form,
# not decorator). Only honoured when the receiver name is in
# MCP_INSTANCE_NAMES AND module_is_mcp gate is True.
MCP_REGISTRATION_ATTRS: list[str] = ["add_tool", "tool"]

# FIX A v1 ANTI-FP (v0.5.0) — observability helper exclusion list.
# When tracing inter-procedural side effects, calls to functions matching any
# of these substrings are NEVER followed. They are pure observability /
# logging / metrics / tracing concerns and would otherwise inject FAKE
# side-effects (audit_log.insert, metrics.record, ...) into otherwise read-
# only tools. Match is case-insensitive substring against the callee's name
# (last attribute or function name).
HELPER_CALL_EXCLUDE_PATTERNS: list[str] = [
    "log_", "_log",
    "audit_", "_audit",
    "track_", "_track",
    "record_", "_record", "record_event", "report_event",
    "emit_", "_emit",
    "metric", "_metric",
    "trace_", "_trace",
    "monitor_", "_monitor",
    "telemetry",
    "report_metric", "report_metrics",
]

# v0.5.2 GATE 1 — benign call name allow-lists for unresolved-effect-carrier
# detection. Conservative by design (the spec biases toward OPAQUE when in
# doubt). Used ONLY by _has_unresolved_effect_carrier to avoid flagging
# stdlib pure-format / introspection / logging calls.
BENIGN_BUILTIN_NAMES: frozenset[str] = frozenset({
    # Type constructors / conversions
    "bool", "bytes", "bytearray", "complex", "dict", "float", "frozenset",
    "int", "list", "memoryview", "object", "range", "set", "slice", "str",
    "tuple", "type",
    # Predicates / iterables
    "all", "any", "callable", "isinstance", "issubclass", "hasattr",
    "iter", "next", "len", "min", "max", "sum", "abs", "divmod",
    "enumerate", "zip", "filter", "map", "reversed", "sorted",
    # Conversion / formatting
    "ascii", "bin", "chr", "format", "hash", "hex", "id", "oct",
    "ord", "repr", "round", "vars", "dir",
    # Attribute access (read)
    "getattr",
    # Pure data ops
    "asdict", "astuple", "field",
    # Standard exception constructors that may appear as raise expr in args
    "exception",
})

# Pure attribute methods on stdlib types (str / list / dict / set / tuple).
# An attribute call whose method name is in this set is treated as benign.
# Also used when the receiver type is not bound (e.g. literals). Only names
# that are NEVER an external side effect. Do NOT add: send, write, execute*,
# run, post — those remain carriers.

# Known builtin types whose method calls are never external side effects.
BUILTIN_TYPES: frozenset[str] = frozenset({
    "str", "bytes", "int", "float", "bool", "complex",
    "list", "dict", "set", "frozenset", "tuple", "bytearray",
})

BENIGN_ATTR_METHODS: frozenset[str] = frozenset({
    # str methods (all pure)
    "upper", "lower", "title", "strip", "lstrip", "rstrip",
    "split", "rsplit", "splitlines", "partition", "rpartition",
    "join", "replace",
    "startswith", "endswith", "count", "encode", "decode",
    "format", "format_map", "casefold", "capitalize", "swapcase",
    "zfill", "expandtabs", "ljust", "rjust", "center",
    "isalpha", "isalnum", "isdigit", "isdecimal", "isnumeric",
    "isspace", "istitle", "isupper", "islower", "isprintable",
    "isidentifier", "isascii",
    # dict / list / set read methods
    "get", "keys", "values", "items", "copy",
    # list / set in-memory mutation (no external side effect)
    "append", "extend", "pop", "add", "update",
    "insert", "remove", "clear", "discard",
    # json / serialization (no I/O)
    "dumps", "loads",
    # pathlib / Path joinpath (pure path math)
    "joinpath",
    # ast / typing / inspect introspection
    "unparse", "parse",
    # find / index — string lookups (pure read)
    "find", "rfind", "index", "rindex",
})

# Benign receiver/object names — attribute calls on these receivers are
# considered observability / pure-stdlib and excluded from carrier flagging.
BENIGN_RECEIVERS: frozenset[str] = frozenset({
    # Logging / observability
    "logger", "log", "logging",
    "ctx", "context", "tracer", "span", "meter", "metrics",
    "telemetry", "audit",
    # Stdlib pure modules (no I/O unless explicit attr we recognize)
    "time", "datetime", "math", "random",
    "json", "yaml", "toml", "csv", "re", "base64", "hashlib", "uuid",
    "itertools", "functools", "collections", "typing", "dataclasses",
    "enum", "abc", "copy", "warnings", "ast", "inspect",
    # Path types — actual writes carry recognized signatures (Path.write_text,
    # Path.unlink, …) which the SideEffectVisitor catches. The receiver Name
    # alone is benign.
    "path", "pathlib",
})

SIDE_EFFECT_PATTERNS: list[dict] = [
    # -----------------------------------------------------------------------
    # Payment / Financial
    # NOTE: name_contains patterns like "refund", "charge" may match
    # internal business methods (e.g. quota_charge.refund()) that are not
    # actual payment operations. Known false positive rate: ~22% on payment
    # patterns across 16 real repos. Acceptable trade-off vs missing real
    # payment calls.
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
        # Also exclude SET TRANSACTION (read-only transaction setup, not a mutation).
        # Do NOT add bare "SET" — SET search_path / SET role mutate session state.
        "category": "database_write",
        "risk": 2,
        "match": {
            "obj_contains": ["session", "db", "conn", "connection"],
            "attr_exact": ["execute", "executemany"],
            "first_arg_excludes": ["select"],
            "sql_excludes": ["SELECT", "SET TRANSACTION"],
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
        # asyncio.create_subprocess_exec / loop.create_subprocess_exec
        # Covers: await asyncio.create_subprocess_exec(...)
        #         process = loop.create_subprocess_exec(...)
        "category": "destructive",
        "risk": 3,
        "match": {
            "attr_exact": ["create_subprocess_exec", "create_subprocess_shell"],
        },
    },
    {
        # bare-name import: from asyncio import create_subprocess_exec
        "category": "destructive",
        "risk": 3,
        "match": {
            "name_contains": ["create_subprocess_exec", "create_subprocess_shell"],
        },
    },
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "name_contains": ["shutdown", "kill_process", "reboot",
                              "format_disk", "wipe", "reset_factory"],
        },
    },
    {
        # Catch x.terminate() exactly — attr_exact prevents terminate_session(),
        # terminate_transaction(), etc. from matching (FIX C v0.5.0 precision).
        "category": "destructive",
        "risk": 3,
        "match": {
            "attr_exact": ["terminate"],
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
    # FIX C (v0.5.0) — psutil process control
    # Process(pid).kill() / .terminate() / .suspend() — irreversible signals
    # to a chosen pid. obj_contains restricted to psutil-related receivers,
    # obj_exact for short receivers like "process" / "proc". attr_exact (not
    # attr_contains) avoids matching reader methods like get_terminated_at()
    # or terminate_session(). Note: a bare animation_proc.kill() in a module
    # that does NOT import psutil will not match (obj_contains is psutil-
    # scoped and obj_exact is restricted to "process"/"proc").
    # -----------------------------------------------------------------------
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "obj_contains": ["psutil", "psutil.process"],
            "attr_exact": ["kill", "terminate", "suspend"],
        },
    },
    {
        "category": "destructive",
        "risk": 3,
        "match": {
            "obj_exact": ["process", "proc"],
            "attr_exact": ["kill", "terminate", "suspend"],
        },
    },
    {
        # FIX C (v0.5.0) — os.kill / os.killpg signal a chosen pid.
        # name_contains uses substring match, so this also catches os.killpg
        # which is acceptable: killpg is destructive too.
        "category": "destructive",
        "risk": 3,
        "match": {
            "name_contains": ["os.kill"],
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
            "obj_contains": ["graph", "chain", "pipeline", "agent", "workflow", "runnable",
                              "compile", "app"],
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
    {
        # OpenAI Agents SDK: Runner.run_sync(), Runner.run()
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "obj_contains": ["runner"],
            "attr_exact": ["run_sync", "run"],
        },
    },
    {
        # CrewAI: crew.kickoff(), crew.kickoff_async(), crew.kickoff_for_each()
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "obj_contains": ["crew"],
            "attr_exact": ["kickoff", "kickoff_async", "kickoff_for_each"],
        },
    },
    {
        # AutoGen / AG2: assistant.initiate_chat(), user_proxy.initiate_chat()
        # No obj_contains: object name varies (assistant, user_proxy, manager, etc.)
        # initiate_chat is specific enough to avoid false positives
        "category": "agent_invocation",
        "risk": 2,
        "match": {
            "attr_exact": ["initiate_chat"],
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

    # -----------------------------------------------------------------------
    # v0.5.2 GATE 6 — narrow SDK verb breadth additions.
    # These are high-signal, receiver-agnostic verbs that distinctly indicate a
    # side effect on their own. attr_exact only — keeps the false-positive
    # surface small. Each verb is documented with its primary SDK source.
    # -----------------------------------------------------------------------
    {
        # asyncpg, psycopg, sqlalchemy async driver — parameterised query exec.
        # Treated as database_write because parameter binding is the common
        # pattern for INSERT / UPDATE / DELETE statements; honest floor lets
        # the OPAQUE path catch the few read-only cases.
        "category": "database_write",
        "risk": 2,
        "match": {
            "attr_exact": ["execute_query", "execute_param_query"],
        },
    },
    {
        # Raw socket / SSH client / RPC channel writes. sendall is unambiguous
        # (no read variant); send_command on a transport is always egress.
        "category": "destructive",
        "risk": 3,
        "match": {
            "attr_exact": ["sendall", "send_command"],
        },
    },
    {
        # AWS Step Functions / Temporal / Argo workflows — kicks off a remote
        # state machine that runs unsupervised. Irreversible once started.
        "category": "destructive",
        "risk": 3,
        "match": {
            "attr_exact": ["start_execution"],
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

# FIX 2 — reader method prefixes: if the final attribute of a call starts
# with one of these prefixes it is treated as read-only, regardless of the
# receiver object name. This overrides the http_write obj_contains heuristic
# so that `client.get_post()` is not flagged as a side effect.
# Do NOT add: update_, create_, delete_, post_, send_ — those are writes.
READER_METHOD_PREFIXES: tuple[str, ...] = (
    "get_", "list_", "read_", "fetch_",
    "search_", "query_", "find_", "describe_", "show_",
)

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
    "evals", "eval", "evaluation", "evaluations",
    "demos", "demo", "samples", "sample",
    "playground", "notebooks", "notebook",
    "tutorials", "tutorial",
    "docs", "doc", "scripts",
})

# File patterns to exclude from scanning
EXCLUDED_FILE_PATTERNS: tuple[str, ...] = (
    "test_",
    "_test.py",
    "conftest.py",
)

# ---------------------------------------------------------------------------
# Inter-procedural decorator body analysis patterns
# ---------------------------------------------------------------------------

INTER_PROC_AUTH_RAISE_VOCAB: frozenset[str] = frozenset({
    "autherror", "authorizationerror", "authenticationerror", "authfailed",
    "notauthenticated", "unauthenticated", "permissionerror", "permissiondenied",
    "accessdenied", "forbidden", "unauthorized", "httperror", "httpexception", "abort",
})

INTER_PROC_AUTH_CONDITION_VOCAB: frozenset[str] = frozenset({
    "current_user", "is_authenticated", "is_authorized", "has_permission",
    "is_logged_in", "authenticated", "authorized", "verify_token",
    "check_permission", "get_current_user",
})

INTER_PROC_RATE_LIMIT_VOCAB: frozenset[str] = frozenset({
    "rate_limit", "ratelimit", "throttle", "limiter", "check_rate", "is_limited", "slowapi", "limits",
})
