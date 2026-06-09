"""AST-based scanner for detecting side effects and guards in Python files.

Mode 1: auto-detection. Walks all .py files in a directory, parses AST,
finds functions with side effects and their governance mechanisms.
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

from diplomat_agent.models import Guard, SideEffect, Tool
from diplomat_agent.scanner.interprocedural import PackageIndex
from diplomat_agent.scanner.patterns import (
    EXCLUDED_DIRS,
    EXCLUDED_FILE_PATTERNS,
    GUARD_PATTERNS,
    HELPER_CALL_EXCLUDE_PATTERNS,
    MCP_CLIENT_IMPORTS,
    MCP_CLIENT_SESSION_NAMES,
    MCP_DISPATCH_DECORATOR_ATTRS,
    MCP_INSTANCE_NAMES,
    MCP_REGISTRATION_ATTRS,
    MCP_SERVER_IMPORTS,
    MCP_TOOL_DECORATOR_ATTRS,
    ORCHESTRATOR_DECORATORS,
    READ_ONLY_PATTERNS,
    READER_METHOD_PREFIXES,
    SIDE_EFFECT_PATTERNS,
)

# ---------------------------------------------------------------------------
# Pattern dispatch index (module-level, built once at import time)
# ---------------------------------------------------------------------------
# For each SIDE_EFFECT_PATTERN that has 'attr_exact', we index it under each
# of its attr values so visit_Call only needs to check patterns whose attr
# could actually match — reducing per-Call pattern checks from ~30 to ~2.
# Patterns without 'attr_exact' are always checked (stored in _ATTR_NONE_PATTERNS).
_ATTR_EXACT_DISPATCH: dict[str, list[dict]] = {}
_ATTR_NONE_PATTERNS: list[dict] = []
for _p in SIDE_EFFECT_PATTERNS:
    _m = _p.get("match", {})
    if "attr_exact" in _m:
        for _a in _m["attr_exact"]:
            _ATTR_EXACT_DISPATCH.setdefault(_a.lower(), []).append(_p)
    else:
        _ATTR_NONE_PATTERNS.append(_p)
del _p, _m, _a  # cleanup loop variables


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src(node: ast.AST, source_lines: list[str]) -> str:
    """Return a short code excerpt for a node (best-effort, max 80 chars)."""
    try:
        line_no = node.lineno - 1  # type: ignore[attr-defined]
        raw = source_lines[line_no].strip()
        return raw[:120]
    except (AttributeError, IndexError):
        return ast.unparse(node)[:120]


def _call_parts(node: ast.Call) -> tuple[str, str, str]:
    """Return (full_name, obj_name, attr_name) for a Call node.

    Examples:
        stripe.Refund.create(...)  → ("stripe.Refund.create", "stripe.refund", "create")
        session.commit()           → ("session.commit", "session", "commit")
        send_mail(...)             → ("send_mail", "", "send_mail")
        self.repo.create(...)      → ("self.repo.create", "self.repo", "create")
        Repository(s).create(...)  → ("repository.create", "repository", "create")
    """
    func = node.func
    if isinstance(func, ast.Attribute):
        attr = func.attr
        value = func.value
        # Build full dotted name for the receiver
        parts: list[str] = []
        cur: ast.expr = value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        elif isinstance(cur, ast.Call):
            # Constructor call: ClassName(args).method()
            ctor = cur.func
            if isinstance(ctor, ast.Name):
                parts.append(ctor.id)
            elif isinstance(ctor, ast.Attribute):
                parts.append(ctor.attr)
        parts.reverse()
        obj = ".".join(parts)
        full = f"{obj}.{attr}" if obj else attr
        return full.lower(), obj.lower(), attr.lower()
    elif isinstance(func, ast.Name):
        name = func.id.lower()
        return name, "", name
    else:
        return "", "", ""


def _kwarg_names(node: ast.Call) -> set[str]:
    """Return the set of keyword argument names for a call."""
    return {kw.arg.lower() for kw in node.keywords if kw.arg}


def _first_arg_str(node: ast.Call) -> str:
    """Return the first positional argument as a string, uppercased.

    Handles plain string literals, f-strings, and text("...") wrapper calls.
    """
    if not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value.upper()
    # F-string: join the constant fragment parts
    if isinstance(first, ast.JoinedStr):
        parts: list[str] = []
        for value in first.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return " ".join(parts).upper()
    # text("...") wrapper — extract the inner string
    if isinstance(first, ast.Call):
        call_name = _call_func_name(first)
        if call_name in ("text", "sa.text", "sqlalchemy.text"):
            if first.args and isinstance(first.args[0], ast.Constant) and isinstance(first.args[0].value, str):
                return first.args[0].value.upper()
    return ""


def _first_arg_call_name(node: ast.Call) -> str:
    """Return the root function name of the first arg if it's a call chain, lowercased.

    e.g. session.execute(select(...))                → "select"
         session.execute(select(User).where(...))    → "select"
         session.execute(insert(...).values(...))     → "insert"
    """
    if not node.args:
        return ""
    first = node.args[0]
    # Walk through chained method calls to find the root call
    # e.g. select(User).where(...) → the root is select(User)
    while isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute):
        first = first.func.value
    if isinstance(first, ast.Call):
        return _call_func_name(first)
    return ""


def _call_func_name(node: ast.Call) -> str:
    """Return the simple function name of a Call node, lowercased."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id.lower()
    if isinstance(func, ast.Attribute):
        return func.attr.lower()
    return ""


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


def _matches_pattern(
    call: ast.Call,
    match: dict,
    source_lines: list[str],
    _full: str | None = None,
    _obj: str | None = None,
    _attr: str | None = None,
) -> bool:
    """Return True if an ast.Call node matches the given pattern match dict.

    Accepts optional pre-computed (_full, _obj, _attr) from _call_parts to
    avoid re-computing them when the caller already has the values.
    """
    if _full is None:
        _full, _obj, _attr = _call_parts(call)
    full_name, obj_name, attr_name = _full, _obj, _attr

    # func_contains: full dotted name must include one of the strings
    if "func_contains" in match:
        if not any(s.lower() in full_name for s in match["func_contains"]):
            return False

    # name_contains: same as func_contains (alias)
    if "name_contains" in match:
        if not any(s.lower() in full_name for s in match["name_contains"]):
            return False

    # obj_contains: the object/receiver name must include one of the strings
    if "obj_contains" in match:
        if not any(s.lower() in obj_name for s in match["obj_contains"]):
            return False

    # obj_exact: the full obj name must exactly equal one of the strings
    # (useful for short names like "ses", "db" where substring matching is too broad)
    if "obj_exact" in match:
        if not any(obj_name == s.lower() for s in match["obj_exact"]):
            return False

    # attr_contains: the attribute (method) name must include one of the strings
    if "attr_contains" in match:
        if not any(s.lower() in attr_name for s in match["attr_contains"]):
            return False

    # attr_exact: the attribute name must exactly equal one of the strings
    if "attr_exact" in match:
        if not any(attr_name == s.lower() for s in match["attr_exact"]):
            return False

    # first_arg_excludes: if first arg is a call to one of these functions, skip (read-only)
    if "first_arg_excludes" in match:
        arg_call = _first_arg_call_name(call)
        if arg_call and arg_call in {s.lower() for s in match["first_arg_excludes"]}:
            return False

    # sql_contains: first arg (string) must contain one of the SQL keywords
    if "sql_contains" in match:
        first_arg = _first_arg_str(call)
        if not any(s.upper() in first_arg for s in match["sql_contains"]):
            return False

    # sql_excludes: if first arg string starts with one of these, skip (read-only)
    if "sql_excludes" in match:
        first_arg = _first_arg_str(call)
        if first_arg and any(first_arg.lstrip().startswith(s.upper()) for s in match["sql_excludes"]):
            return False

    # kwarg_contains: call must have at least one of these kwargs
    if "kwarg_contains" in match:
        kws = _kwarg_names(call)
        if not any(k.lower() in kws for k in match["kwarg_contains"]):
            return False

    return True


def _is_read_only(call: ast.Call) -> bool:
    """Return True if a call is read-only.

    A call is read-only when:
    1. Its final attribute starts with a reader-method prefix (FIX 2), OR
    2. It matches one of the explicit READ_ONLY_PATTERNS.

    Reader-prefix check takes priority so that `client.get_post()` is never
    flagged by the http_write pattern via obj_contains heuristics.
    """
    _, _, attr_name = _call_parts(call)
    if attr_name and any(attr_name.startswith(p) for p in READER_METHOD_PREFIXES):
        return True
    for pattern in READ_ONLY_PATTERNS:
        if _matches_pattern(call, pattern["match"], []):
            return True
    return False


# ---------------------------------------------------------------------------
# Guard detection from decorators, imports, and function body
# ---------------------------------------------------------------------------


class _GuardVisitor(ast.NodeVisitor):
    """Visits a function body and decorators to collect Guard objects."""

    def __init__(self, source_lines: list[str], imports: set[str]) -> None:
        self.source_lines = source_lines
        self.imports = imports  # module-level import names (lowercased)
        self.guards: list[Guard] = []

    def _add_guard(self, guard_type: str, coverage: str, node: ast.AST) -> None:
        evidence = _src(node, self.source_lines)
        line = getattr(node, "lineno", 0)
        self.guards.append(Guard(type=guard_type, evidence=evidence, line=line, coverage=coverage))

    def _check_call_against_guard_patterns(self, node: ast.Call) -> None:
        full_name, _obj, _attr = _call_parts(node)
        kws = _kwarg_names(node)

        for pattern in GUARD_PATTERNS:
            match = pattern["match"]
            # func_contains / name_contains
            if "func_contains" in match:
                if any(s.lower() in full_name for s in match["func_contains"]):
                    # Also check kwarg_contains if present
                    if "kwarg_contains" in match:
                        if any(k.lower() in kws for k in match["kwarg_contains"]):
                            self._add_guard(pattern["type"], pattern["coverage"], node)
                    else:
                        self._add_guard(pattern["type"], pattern["coverage"], node)

            if "name_contains" in match:
                if any(s.lower() in full_name for s in match["name_contains"]):
                    self._add_guard(pattern["type"], pattern["coverage"], node)

            if "kwarg_contains" in match and "func_contains" not in match and "name_contains" not in match:
                if any(k.lower() in kws for k in match["kwarg_contains"]):
                    self._add_guard(pattern["type"], pattern["coverage"], node)

    def visit_Call(self, node: ast.Call) -> None:
        self._check_call_against_guard_patterns(node)
        self.generic_visit(node)

    # Auth-related names that indicate a manual auth check in an if condition
    _AUTH_IF_INDICATORS: frozenset[str] = frozenset({
        "current_user", "is_authenticated", "request.user", "get_current_user",
        "verify_token", "check_permission", "is_authorized", "has_permission",
        "authenticated", "authorization",
    })

    def visit_If(self, node: ast.If) -> None:
        """Detect manual if-based validation and auth checks (partial coverage)."""
        compare = ast.unparse(node.test).lower()

        # Input validation: if condition mentions a bound-related variable
        for pattern in GUARD_PATTERNS:
            match = pattern["match"]
            if "compare_contains" in match and pattern["type"] == "input_validation":
                if any(s.lower() in compare for s in match["compare_contains"]):
                    self._add_guard("input_validation", "partial", node)
                    break

        # Auth check: if condition tests an auth-related name
        if any(indicator in compare for indicator in self._AUTH_IF_INDICATORS):
            self._add_guard("auth_check", "partial", node)

        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Detect assert-based validation."""
        compare = ast.unparse(node.test).lower()
        for pattern in GUARD_PATTERNS:
            match = pattern["match"]
            if "compare_contains" in match and pattern["type"] == "input_validation":
                if any(s.lower() in compare for s in match["compare_contains"]):
                    self._add_guard("input_validation", "partial", node)
                    break
        self.generic_visit(node)


def _detect_decorator_guards(
    decorators: list[ast.expr],
    source_lines: list[str],
    from_file: Path | None = None,
    package_index: "PackageIndex | None" = None,
) -> list[Guard]:
    """Detect guards from decorators (name-based first, then inter-procedural)."""
    guards: list[Guard] = []
    for dec in decorators:
        dec_str = ast.unparse(dec).lower()
        matched_by_name = False
        for pattern in GUARD_PATTERNS:
            match = pattern["match"]
            if "decorator_contains" in match:
                if any(s.lower() in dec_str for s in match["decorator_contains"]):
                    guards.append(Guard(type=pattern["type"], evidence=_src(dec, source_lines), line=getattr(dec, "lineno", 0), coverage=pattern["coverage"]))
                    matched_by_name = True
        if not matched_by_name and package_index is not None and from_file is not None:
            guards.extend(package_index.resolve_decorator_guards(dec, from_file))
    return guards


def _detect_import_guards(imports: set[str], file_path: str) -> list[Guard]:
    """Detect guards from module-level imports (e.g. rate limiting libraries)."""
    guards: list[Guard] = []
    for pattern in GUARD_PATTERNS:
        match = pattern["match"]
        if "import_contains" in match:
            for imp in imports:
                if any(s.lower() in imp for s in match["import_contains"]):
                    guards.append(
                        Guard(
                            type=pattern["type"],
                            evidence=f"import {imp}",
                            line=0,
                            coverage=pattern["coverage"],
                        )
                    )
                    break
    return guards


def _detect_depends_guards(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
) -> list[Guard]:
    """Detect FastAPI Depends() auth guards from function parameter defaults."""
    guards: list[Guard] = []
    args = func_node.args

    # Collect all (arg, default) pairs.
    # args.defaults is right-aligned to args.args:
    #   if args.args has 4 items and defaults has 2, defaults[0] maps to args.args[2].
    defaults: list[tuple[ast.arg, ast.expr | None]] = []
    n_args = len(args.args)
    n_defaults = len(args.defaults)
    offset = n_args - n_defaults
    for i, arg in enumerate(args.args):
        default = args.defaults[i - offset] if i >= offset else None
        defaults.append((arg, default))
    # kw_defaults is 1:1 with kwonlyargs (None for no default)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        defaults.append((arg, default))

    for arg, default in defaults:
        if default is None or not isinstance(default, ast.Call):
            continue
        func = default.func
        is_depends = (
            (isinstance(func, ast.Name) and func.id in ("Depends", "Security"))
            or (isinstance(func, ast.Attribute) and func.attr in ("Depends", "Security"))
        )
        if not is_depends:
            continue
        inner = ast.unparse(default.args[0]) if default.args else "..."
        func_name = func.id if isinstance(func, ast.Name) else func.attr
        evidence = f"{func_name}({inner})"
        line = getattr(default, "lineno", func_node.lineno)
        guards.append(
            Guard(type="auth_check", evidence=evidence, line=line, coverage="full")
        )

    return guards


# ---------------------------------------------------------------------------
# Side-effect detection
# ---------------------------------------------------------------------------


class _SideEffectVisitor(ast.NodeVisitor):
    """Visits a function body to collect SideEffect objects."""

    def __init__(self, source_lines: list[str], file_path: str) -> None:
        self.source_lines = source_lines
        self.file_path = file_path
        self.side_effects: list[SideEffect] = []
        self._seen: set[tuple[str, int]] = set()  # dedup by (category, line)

    def visit_Call(self, node: ast.Call) -> None:
        # Pre-compute call parts ONCE; pass to _matches_pattern to avoid
        # redundant _call_parts calls across the ~30 SIDE_EFFECT_PATTERNS.
        full_name, obj_name, attr_name = _call_parts(node)
        # FIX 2 — reader-method prefix guard: skip attribute calls whose method
        # name starts with a read-only prefix (e.g. get_, list_, fetch_).
        # Restricted to attribute calls (obj.method()) so that standalone
        # function calls like call_llm() or get_llm_response() are never
        # suppressed by this rule.
        if obj_name and attr_name and any(
            attr_name.startswith(p) for p in READER_METHOD_PREFIXES
        ):
            self.generic_visit(node)
            return
        # Dispatch: only check patterns where attr_exact matches (or no
        # attr_exact constraint).  For most Call nodes with a non-matching
        # attr, _ATTR_EXACT_DISPATCH.get() returns [], so we only iterate
        # the small _ATTR_NONE_PATTERNS list — a ~15× reduction in work.
        candidates: list[dict]
        if attr_name:
            exact_matches = _ATTR_EXACT_DISPATCH.get(attr_name, ())
            if exact_matches or _ATTR_NONE_PATTERNS:
                candidates = list(_ATTR_NONE_PATTERNS) + list(exact_matches)
            else:
                self.generic_visit(node)
                return
        else:
            candidates = _ATTR_NONE_PATTERNS
        for pattern in candidates:
            if _matches_pattern(
                call=node,
                match=pattern["match"],
                source_lines=self.source_lines,
                _full=full_name,
                _obj=obj_name,
                _attr=attr_name,
            ):
                key = (pattern["category"], node.lineno)
                if key not in self._seen:
                    self._seen.add(key)
                    self.side_effects.append(
                        SideEffect(
                            category=pattern["category"],
                            evidence=_src(node, self.source_lines),
                            line=node.lineno,
                            file=self.file_path,
                            type=pattern["category"],
                        )
                    )
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Module-level import collection
# ---------------------------------------------------------------------------


def _collect_imports(tree: ast.Module) -> set[str]:
    """Return a set of all imported module names (lowercased) in a module."""
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.lower())
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.lower())
    return imports


# ---------------------------------------------------------------------------
# FIX A v1 (v0.5.0) — Inter-procedural side-effect / guard resolution
# ---------------------------------------------------------------------------
# Periphery v1 (verrouillé):
#   - Resolves ONLY same-package top-level functions (PackageIndex._defs only
#     indexes top-level FunctionDef / AsyncFunctionDef). Class methods are NOT
#     resolved in v1 — that is FIX A v2 (separate workstream).
#   - Resolves ONLY calls whose return value is used (Assign / Return / nested
#     in expression). Statement-only `helper(x)` lines are NOT followed —
#     these are typical fire-and-forget observability calls.
#   - Calls whose name matches HELPER_CALL_EXCLUDE_PATTERNS are NEVER followed
#     even if the return value is used.
#   - Helper guards (decorator + body) are propagated alongside side effects
#     (mandatory symmetry — a helper that validates-then-writes must NOT be
#     reported as UNGUARDED on its caller).
#   - Bounded depth (default 2, hard cap 3), cycle protection via visited set,
#     memoization via PackageIndex._effects_cache.

_DEFAULT_INTERPROC_DEPTH: int = 2
_HARD_INTERPROC_DEPTH_CAP: int = 3


def _is_excluded_helper_name(name: str) -> bool:
    """Return True if a callee name matches an observability-helper exclusion pattern.

    Match is case-insensitive substring. Used by FIX A v1 to refuse to follow
    into logging / audit / metrics / tracing helpers that would inject fake
    side-effects into otherwise read-only tools.
    """
    if not name:
        return False
    low = name.lower()
    for pattern in HELPER_CALL_EXCLUDE_PATTERNS:
        if pattern.lower() in low:
            return True
    return False


class _EligibleCallVisitor(ast.NodeVisitor):
    """Collect plain-name Call nodes whose return value is used.

    Only collects calls whose function is a bare ``Name`` node (i.e.
    ``helper(x)``, ``_purge(y)``). Attribute calls (``obj.method()``)
    are intentionally skipped: in FIX A v1 (same-module top-level only)
    they can never resolve to a local top-level def and generating a
    resolution attempt for every ``result.strip()`` / ``path.resolve()``
    was the main source of scan slowdown on large repos (O(N*M) lookups).

    A statement-only ``Expr(Call(...))`` is REJECTED (typical fire-and-forget
    observability pattern). Calls in argument lists of a statement-only call
    are still collected because their results are consumed by the outer call.
    """

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Expr(self, node: ast.Expr) -> None:
        # Skip the OUTER call directly wrapped by Expr (statement-only),
        # but descend into its argument expressions so nested calls whose
        # results feed the outer call are still considered.
        if isinstance(node.value, ast.Call):
            for arg in node.value.args:
                self.visit(arg)
            for kw in node.value.keywords:
                self.visit(kw.value)
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # v1: only follow plain-name calls — skip attribute calls entirely.
        if isinstance(node.func, ast.Name):
            self.calls.append(node)
        # Always recurse into arguments so nested plain-name calls are found.
        self.generic_visit(node)


def _resolve_call_effects(
    call: ast.Call,
    from_file: str,
    package_index: "PackageIndex | None",
    depth: int,
    max_depth: int,
    visited: set[tuple[str, str]],
    source_lines_cache: dict[str, list[str]],
) -> tuple[list[SideEffect], list[Guard]]:
    """Resolve a Call → return (side_effects, guards) collected from callee body.

    See module-level FIX A v1 docstring for the verrouillé peripheral. Returns
    empty lists when:
      - depth >= max_depth
      - callee is unresolvable, or out of package root
      - cycle detected (visited)
      - callee name matches HELPER_CALL_EXCLUDE_PATTERNS
    """
    if package_index is None:
        return [], []
    if depth >= max_depth:
        return [], []

    # Determine the callee name we will resolve. v1: plain Name calls only.
    # Attribute calls (obj.method()) are never resolvable to same-module
    # top-level defs — skip them early for correctness and performance.
    full_name, obj_name, attr_name = _call_parts(call)
    if obj_name:
        return [], []

    callee_name = full_name  # plain Name call: full_name == attr_name == func.id
    if not callee_name:
        return [], []

    # ANTI-FP: observability-helper exclusion (applied BEFORE _lookup_def).
    if _is_excluded_helper_name(callee_name):
        return [], []

    # Resolve via PackageIndex (top-level functions only, by design).
    callee_def, callee_file = package_index._lookup_def(
        callee_name, Path(from_file)
    )
    if callee_def is None:
        return [], []

    # Stop at stdlib / third-party (anything outside the package root).
    # Resolve callee_file to normalise Windows short-paths (GUARNE~1 → guarnelli)
    # before comparing to package_index.root (which is always the long-path form).
    import os as _os
    try:
        callee_resolved = callee_file.resolve()
    except (OSError, ValueError):
        callee_resolved = callee_file
    callee_norm = _os.path.normcase(str(callee_resolved))
    root_norm = _os.path.normcase(str(package_index.root))
    if not callee_norm.startswith(root_norm):
        return [], []

    callee_path_str = str(callee_file)
    visit_key = (callee_path_str, callee_def.name)

    # Cycle protection.
    if visit_key in visited:
        return [], []

    # Memoization (PackageIndex-scoped cache).
    cache = getattr(package_index, "_effects_cache", None)
    if cache is not None and visit_key in cache:
        return cache[visit_key]

    # Read source lines for the callee file (cached per-scan).
    if callee_path_str not in source_lines_cache:
        try:
            text = callee_file.read_text(encoding="utf-8-sig", errors="replace")
            source_lines_cache[callee_path_str] = text.splitlines()
        except (OSError, UnicodeDecodeError):
            return [], []
    callee_lines = source_lines_cache[callee_path_str]

    # --- Intra-procedural side effects + body guards of the callee. ---
    se_visitor = _SideEffectVisitor(callee_lines, callee_path_str)
    for stmt in callee_def.body:
        se_visitor.visit(stmt)
    callee_side_effects: list[SideEffect] = list(se_visitor.side_effects)

    g_visitor = _GuardVisitor(callee_lines, set())
    g_visitor.visit(callee_def)
    callee_guards: list[Guard] = list(g_visitor.guards)

    # Decorator guards on the callee (symmetric: a helper decorated with
    # @auth_required still protects its caller's tool).
    callee_dec_guards = _detect_decorator_guards(
        callee_def.decorator_list,
        callee_lines,
        from_file=callee_file,
        package_index=package_index,
    )
    callee_guards.extend(callee_dec_guards)

    # Augment side-effect evidence with [via callee_name() @ file:line].
    try:
        rel = str(callee_file.relative_to(package_index.root))
    except ValueError:
        rel = callee_file.name
    via_label = f"[via {callee_def.name}() @ {rel}:{callee_def.lineno}]"
    callee_side_effects = [
        SideEffect(
            category=se.category,
            evidence=f"{se.evidence}  {via_label}",
            line=se.line,
            file=se.file,
            type=se.type,
        )
        for se in callee_side_effects
    ]

    # --- Recursive descent into eligible sub-calls of the callee. ---
    new_visited = visited | {visit_key}
    sub_visitor = _EligibleCallVisitor()
    for stmt in callee_def.body:
        sub_visitor.visit(stmt)
    for sub_call in sub_visitor.calls:
        sub_se, sub_g = _resolve_call_effects(
            sub_call,
            callee_path_str,
            package_index,
            depth + 1,
            max_depth,
            new_visited,
            source_lines_cache,
        )
        callee_side_effects.extend(sub_se)
        callee_guards.extend(sub_g)

    # Memoize.
    if cache is not None:
        cache[visit_key] = (callee_side_effects, callee_guards)

    return callee_side_effects, callee_guards


# ---------------------------------------------------------------------------
# Function analysis
# ---------------------------------------------------------------------------


def _has_mcp_client_call_tool(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True if the function body contains an <obj>.call_tool(...) call

    where obj.id (lowercased) is one of MCP_CLIENT_SESSION_NAMES
    (session / client / _session).  Only Call nodes are checked — decorators
    are intentionally excluded per GATE 4 spec.
    """
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "call_tool":
            continue
        recv = func.value
        if isinstance(recv, ast.Name) and recv.id.lower() in MCP_CLIENT_SESSION_NAMES:
            return True
    return False


def _parse_tool_annotations(decorator: ast.Call) -> "tuple[bool | None, bool | None]":
    """Parse readOnlyHint and destructiveHint from a @mcp.tool(...) decorator AST node.

    Supports two shapes:
    - @mcp.tool(readOnlyHint=True, destructiveHint=False, ...)
    - @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, ...), ...)

    Returns (readonly_hint, destructive_hint). Any non-Constant boolean value → None.
    Never raises; returns (None, None) on any unexpected structure.
    """
    def _read_bool_kwarg(keywords: list, name: str) -> "bool | None":
        for kw in keywords:
            if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                return kw.value.value
        return None

    readonly: "bool | None" = None
    destructive: "bool | None" = None

    try:
        # Check direct kwargs first: @mcp.tool(readOnlyHint=True, ...)
        readonly = _read_bool_kwarg(decorator.keywords, "readOnlyHint")
        destructive = _read_bool_kwarg(decorator.keywords, "destructiveHint")

        # If not found directly, look inside annotations=ToolAnnotations(...)
        if readonly is None or destructive is None:
            for kw in decorator.keywords:
                if kw.arg == "annotations" and isinstance(kw.value, ast.Call):
                    inner = kw.value
                    if readonly is None:
                        readonly = _read_bool_kwarg(inner.keywords, "readOnlyHint")
                    if destructive is None:
                        destructive = _read_bool_kwarg(inner.keywords, "destructiveHint")
                    break
    except Exception:  # noqa: BLE001
        pass

    return readonly, destructive


def _analyze_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
    file_path: str,
    module_imports: set[str],
    package_index: "PackageIndex | None" = None,
    module_is_mcp: bool = False,
    module_is_mcp_client: bool = False,
    programmatic_mcp_tools: "set[str] | None" = None,
    interproc_source_cache: "dict[str, list[str]] | None" = None,
) -> Tool | None:
    """Analyze a single function/method and return a Tool if it has side effects."""
    # --- Collect intra-procedural side effects (body only, skip decorators) ---
    se_visitor = _SideEffectVisitor(source_lines, file_path)
    for stmt in func_node.body:
        se_visitor.visit(stmt)
    side_effects = list(se_visitor.side_effects)

    # --- FIX A v1 (v0.5.0): inter-procedural side-effect / guard tracing ---
    # Walk eligible sub-calls of the function body (return-value-used only)
    # and merge effects + guards from same-package top-level helpers.
    interproc_guards: list[Guard] = []
    if package_index is not None:
        if interproc_source_cache is None:
            interproc_source_cache = {}
        interproc_source_cache[file_path] = source_lines
        eligible = _EligibleCallVisitor()
        for stmt in func_node.body:
            eligible.visit(stmt)
        for sub_call in eligible.calls:
            extra_se, extra_g = _resolve_call_effects(
                sub_call,
                file_path,
                package_index,
                depth=0,
                max_depth=_DEFAULT_INTERPROC_DEPTH,
                visited=set(),
                source_lines_cache=interproc_source_cache,
            )
            if extra_se:
                side_effects.extend(extra_se)
            if extra_g:
                interproc_guards.extend(extra_g)

    # FIX A v1 dedup — keyed on (file, category, line) to support multi-file
    # tracing without artificial double-counting.
    if side_effects:
        _seen_se: set[tuple[str, str, int]] = set()
        deduped: list[SideEffect] = []
        for se in side_effects:
            key = (se.file, se.category, se.line)
            if key not in _seen_se:
                _seen_se.add(key)
                deduped.append(se)
        side_effects = deduped

    # GATE 4 — MCP client call_tool detection.
    # A function that calls session/client/_session.call_tool(...) in its body
    # is an opaque proxy to a remote MCP server.  It may have no local side
    # effects that our patterns catch, so we must bypass the "no side effects →
    # None" gate for these functions.
    is_mcp_client_proxy = module_is_mcp_client and _has_mcp_client_call_tool(func_node)

    if not side_effects and not is_mcp_client_proxy:
        return None

    # --- Filter out pure read-only functions ---
    # A function is read-only only if ALL its detected patterns are read-only.
    write_effects = [se for se in side_effects if se.category != "read"]
    if not write_effects and not is_mcp_client_proxy:
        return None

    # --- Extract parameters ---
    _NUMERIC_ANNOTATIONS: frozenset[str] = frozenset({
        "int", "float", "decimal", "decimal.decimal",
        "optional[int]", "optional[float]",
    })
    _NUMERIC_NAMES: frozenset[str] = frozenset({
        "amount", "price", "quantity", "count", "total",
        "limit", "max", "size", "fee", "cost", "budget",
    })
    params: list[dict] = []
    args = func_node.args
    all_args = args.args + args.posonlyargs + args.kwonlyargs
    for arg in all_args:
        if arg.arg in ("self", "cls"):
            continue
        type_str = ast.unparse(arg.annotation) if arg.annotation else "unknown"
        is_numeric = (
            type_str.lower() in _NUMERIC_ANNOTATIONS
            or arg.arg.lower() in _NUMERIC_NAMES
        )
        params.append({"name": arg.arg, "type": type_str, "numeric": is_numeric, "has_bounds": False})

    # --- Collect guards ---
    dec_guards = _detect_decorator_guards(func_node.decorator_list, source_lines, from_file=Path(file_path), package_index=package_index)
    imp_guards = _detect_import_guards(module_imports, file_path)
    dep_guards = _detect_depends_guards(func_node, source_lines)

    guard_visitor = _GuardVisitor(source_lines, module_imports)
    guard_visitor.visit(func_node)
    body_guards = guard_visitor.guards

    # Combine, dedup by (type, line, evidence) — evidence disambiguates
    # cross-file helper guards that share a line number with caller guards.
    all_guards: list[Guard] = []
    seen_guards: set[tuple[str, int, str]] = set()
    for g in dec_guards + imp_guards + dep_guards + body_guards + interproc_guards:
        key = (g.type, g.line, g.evidence)
        if key not in seen_guards:
            seen_guards.add(key)
            all_guards.append(g)

    # --- Detect orchestrator decorators (auto-retry risk) ---
    auto_retried = False
    auto_retry_decorator = ""
    for dec in func_node.decorator_list:
        dec_str = ast.unparse(dec).lower()
        # Strip call parens: e.g. "app.task(bind=True)" -> "app.task"
        dec_name = dec_str.split("(")[0]
        for orch in ORCHESTRATOR_DECORATORS:
            if dec_name == orch.lower() or dec_name.endswith("." + orch.lower()):
                auto_retried = True
                auto_retry_decorator = f"@{dec_name}"
                break
        if auto_retried:
            break

    # --- Detect MCP tool / client exposure ---
    # Priority: mcp_client (GATE 4) > mcp_tool (server-side).
    # module_is_mcp_client is only True when module_is_mcp is False (mutually
    # exclusive by construction in scan_file), so the ordering is safe.
    exposure = "internal"
    exposure_evidence = ""
    readonly_hint: "bool | None" = None
    destructive_hint: "bool | None" = None

    # GATE 4 — MCP client: function body contains <session|client|_session>.call_tool(...)
    if is_mcp_client_proxy:
        exposure = "mcp_client"
        # exposure_evidence is the call site line; best-effort from write_effects or body.
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            func_ast = node.func
            if (
                isinstance(func_ast, ast.Attribute)
                and func_ast.attr == "call_tool"
                and isinstance(func_ast.value, ast.Name)
                and func_ast.value.id.lower() in MCP_CLIENT_SESSION_NAMES
            ):
                exposure_evidence = _src(node, source_lines)
                break

    if module_is_mcp and exposure == "internal":
        for dec in func_node.decorator_list:
            dec_unparsed = ast.unparse(dec)
            dec_parts = dec_unparsed.split("(")[0].rsplit(".", 1)
            if len(dec_parts) == 2 and dec_parts[1] in MCP_TOOL_DECORATOR_ATTRS:
                exposure = "mcp_tool"
                exposure_evidence = "@" + dec_unparsed[:80]
                # Parse ToolAnnotations hints from the decorator AST node
                if isinstance(dec, ast.Call):
                    readonly_hint, destructive_hint = _parse_tool_annotations(dec)
                break
        # FIX B v1 (v0.5.0) — programmatic registration via mcp.add_tool(fn)
        # promotes the referenced function to mcp_tool exposure.
        if exposure == "internal" and programmatic_mcp_tools:
            if func_node.name in programmatic_mcp_tools:
                exposure = "mcp_tool"
                exposure_evidence = f"mcp.add_tool({func_node.name}) [programmatic]"

    # --- Detect # diplomat:ok / # canary:ok / # checked:ok inline comments ---
    ignored = False
    ignore_reason = ""
    for se in write_effects:
        line_idx = se.line - 1
        if 0 <= line_idx < len(source_lines):
            line_text = source_lines[line_idx]
            for marker in ("diplomat:ok", "canary:ok", "checked:ok"):
                if marker in line_text:
                    ignored = True
                    # Extract reason after the marker
                    after = line_text.split(marker, 1)[1].strip()
                    # Strip leading punctuation like " — " or " - "
                    for prefix in ("—", "-", "–"):
                        if after.startswith(prefix):
                            after = after[len(prefix):].strip()
                    if after:
                        ignore_reason = after
                    else:
                        ignore_reason = marker
                    break
        if ignored:
            break

    # Also check the function def line and the line above it
    if not ignored:
        for check_line in (func_node.lineno - 1, func_node.lineno - 2):
            if 0 <= check_line < len(source_lines):
                line_text = source_lines[check_line]
                for marker in ("diplomat:ok", "canary:ok", "checked:ok"):
                    if marker in line_text:
                        ignored = True
                        after = line_text.split(marker, 1)[1].strip()
                        for prefix in ("—", "-", "–"):
                            if after.startswith(prefix):
                                after = after[len(prefix):].strip()
                        if after:
                            ignore_reason = after
                        else:
                            ignore_reason = marker
                        break
            if ignored:
                break

    tool = Tool(
        name=func_node.name,
        file=file_path,
        line=func_node.lineno,
        params=params,
        side_effects=write_effects,
        guards=all_guards,
        verdict="UNGUARDED",  # will be computed by analyzer/guards.py
        auto_retried=auto_retried,
        auto_retry_decorator=auto_retry_decorator,
        ignored=ignored,
        ignore_reason=ignore_reason,
        exposure=exposure,
        exposure_evidence=exposure_evidence,
        readonly_hint=readonly_hint,
        destructive_hint=destructive_hint,
    )
    return tool


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------


def scan_file(
    file_path: Path,
    package_index: "PackageIndex | None" = None,
    _parse_errors: "list[str] | None" = None,
    _dispatcher_files: "list[str] | None" = None,
) -> list[Tool]:
    """Parse a single Python file and return all tools found.

    Args:
        file_path: Path to the Python file to scan.
        package_index: Optional package index for interprocedural analysis.
        _parse_errors: If provided, any file that fails to parse (SyntaxError)
            will have its path appended here. Internal use by scan_directory.
        _dispatcher_files: If provided, any file containing a low-level
            @*.call_tool dispatcher will have its path appended here.
    """
    # FIX 1 — use utf-8-sig to silently strip BOM without error
    source = file_path.read_text(encoding="utf-8-sig", errors="replace")
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        print(
            f"\u26a0 could not parse {file_path} (SyntaxError) \u2014 "
            f"skipped, NOT counted as clean",
            file=sys.stderr,
        )
        if _parse_errors is not None:
            _parse_errors.append(str(file_path))
        return []

    module_imports = _collect_imports(tree)

    # Detect MCP server context via import-based gate
    module_is_mcp = bool(module_imports & {s.lower() for s in MCP_SERVER_IMPORTS})

    # GATE 4 — Detect MCP client context.
    # A module is an MCP client when it imports from MCP_CLIENT_IMPORTS AND is
    # not simultaneously an MCP server (the two roles are mutually exclusive in
    # practice and the server imports take precedence).
    module_is_mcp_client = bool(module_imports & MCP_CLIENT_IMPORTS) and not module_is_mcp

    # FIX 3 — extended gate: detect @<name>.tool() in files that import an MCP
    # instance from a local/shared module (e.g. `from .server import mcp`).
    # Without this, files like `src/tools/redis_tools.py` that do
    # `from src.common.server import mcp` are not recognised as MCP modules.
    if not module_is_mcp:
        imported_mcp_names: set[str] = set()
        for _node in ast.walk(tree):
            if isinstance(_node, ast.ImportFrom):
                for _alias in _node.names:
                    _sym = (_alias.asname if _alias.asname else _alias.name).lower()
                    if _sym in MCP_INSTANCE_NAMES:
                        imported_mcp_names.add(_sym)
        if imported_mcp_names:
            for _node in ast.walk(tree):
                if module_is_mcp:
                    break
                if isinstance(_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for _dec in _node.decorator_list:
                        _dec_parts = ast.unparse(_dec).split("(")[0].rsplit(".", 1)
                        if (
                            len(_dec_parts) == 2
                            and _dec_parts[0].lower() in imported_mcp_names
                            and _dec_parts[1] in MCP_TOOL_DECORATOR_ATTRS
                        ):
                            module_is_mcp = True
                            break

    # Warn once per file when a low-level @.call_tool dispatcher is present.
    # Per-tool resolution for this pattern is not supported in v1; FastMCP
    # @mcp.tool is fully supported.
    if module_is_mcp:
        _found_dispatch = False
        for _node in ast.walk(tree):
            if _found_dispatch:
                break
            if isinstance(_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for _dec in _node.decorator_list:
                    _dec_parts = ast.unparse(_dec).split("(")[0].rsplit(".", 1)
                    if len(_dec_parts) == 2 and _dec_parts[1] in MCP_DISPATCH_DECORATOR_ATTRS:
                        print(
                            f"\u26a0 low-level MCP dispatcher detected (@server.call_tool) in "
                            f"{file_path} \u2014 per-tool analysis not supported in v1; "
                            f"FastMCP @mcp.tool is fully supported.",
                            file=sys.stderr,
                        )
                        # FIX 4 — track dispatcher files for stats / reporting
                        if _dispatcher_files is not None:
                            _dispatcher_files.append(str(file_path))
                        _found_dispatch = True
                        break

    # FIX B v1 (v0.5.0) — collect programmatically-registered MCP tool names.
    # Recognises mcp.add_tool(fn), server.add_tool(fn), app.tool(fn) when the
    # receiver is in MCP_INSTANCE_NAMES AND module_is_mcp gate is True. The
    # first positional arg must be a Name or Attribute referring to a local
    # top-level function. Resolved names go into programmatic_mcp_tools so
    # _analyze_function can promote those defs to exposure="mcp_tool".
    programmatic_mcp_tools: set[str] = set()
    if module_is_mcp:
        for _node in ast.walk(tree):
            if not isinstance(_node, ast.Call):
                continue
            _func = _node.func
            if not isinstance(_func, ast.Attribute):
                continue
            if _func.attr not in MCP_REGISTRATION_ATTRS:
                continue
            # Receiver must be one of MCP_INSTANCE_NAMES (mcp / server / app).
            _recv = _func.value
            if not isinstance(_recv, ast.Name):
                continue
            if _recv.id.lower() not in MCP_INSTANCE_NAMES:
                continue
            if not _node.args:
                continue
            _arg0 = _node.args[0]
            if isinstance(_arg0, ast.Name):
                programmatic_mcp_tools.add(_arg0.id)
            elif isinstance(_arg0, ast.Attribute):
                # Best-effort: foo.bar → bar (last attribute name)
                programmatic_mcp_tools.add(_arg0.attr)

    tools: list[Tool] = []

    # Shared inter-procedural source-line cache for this file scan.
    _interproc_cache: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            tool = _analyze_function(
                func_node=node,
                source_lines=source_lines,
                file_path=str(file_path),
                module_imports=module_imports,
                package_index=package_index,
                module_is_mcp=module_is_mcp,
                module_is_mcp_client=module_is_mcp_client,
                programmatic_mcp_tools=programmatic_mcp_tools,
                interproc_source_cache=_interproc_cache,
            )
            if tool is not None:
                tools.append(tool)

    return tools


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------


def _should_exclude_dir(dir_name: str) -> bool:
    """Return True if the directory should be excluded from scanning."""
    return dir_name in EXCLUDED_DIRS or dir_name.startswith(".")


def _should_exclude_file(file_path: Path) -> bool:
    """Return True if the file should be excluded from scanning.

    Excludes test_*.py / *_test.py / conftest.py by filename. Directory-level
    exclusions (tests/, fixtures/, venv/, etc.) are handled by _should_exclude_dir
    during traversal, so we only need to check the filename here.
    """
    name = file_path.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


def scan_directory(root: Path) -> list[Tool]:
    """Recursively scan a directory and return all tools found.

    Excludes venv/, __pycache__/, .git/, node_modules/, migrations/,
    alembic/, test files, and similar.

    After calling this function, the module-level ``last_scan_stats`` dict
    is populated with ``files_scanned``, ``files_skipped``,
    ``files_unparsed``, and ``dispatcher_files`` entries.
    """
    global last_scan_stats
    tools: list[Tool] = []
    files_scanned = 0
    files_skipped = 0
    _parse_errors: list[str] = []
    _dispatcher_files: list[str] = []

    package_index = PackageIndex(root)

    for py_file, included in _iter_all_python_files(root):
        if included:
            file_tools = scan_file(
                py_file,
                package_index=package_index,
                _parse_errors=_parse_errors,
                _dispatcher_files=_dispatcher_files,
            )
            tools.extend(file_tools)
            files_scanned += 1
        else:
            files_skipped += 1

    last_scan_stats = {
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "files_unparsed": _parse_errors,
        "dispatcher_files": _dispatcher_files,
    }
    return tools


# Module-level stats populated by the last scan_directory() call
last_scan_stats: dict = {
    "files_scanned": 0,
    "files_skipped": 0,
    "files_unparsed": [],
    "dispatcher_files": [],
}


def _iter_python_files(root: Path):
    """Yield all .py files under root, respecting exclusion rules."""
    for item in root.iterdir():
        if item.is_dir():
            if not _should_exclude_dir(item.name):
                yield from _iter_python_files(item)
        elif item.is_file() and item.suffix == ".py":
            if not _should_exclude_file(item):
                yield item


def _iter_all_python_files(root: Path):
    """Yield (path, included) for every .py file under root."""
    for item in root.iterdir():
        if item.is_dir():
            if _should_exclude_dir(item.name):
                # Count all .py files in excluded dirs as skipped
                for sub in item.rglob("*.py"):
                    if sub.is_file():
                        yield sub, False
            else:
                yield from _iter_all_python_files(item)
        elif item.is_file() and item.suffix == ".py":
            if _should_exclude_file(item):
                yield item, False
            else:
                yield item, True
