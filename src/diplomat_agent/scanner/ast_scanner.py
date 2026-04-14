"""AST-based scanner for detecting side effects and guards in Python files.

Mode 1: auto-detection. Walks all .py files in a directory, parses AST,
finds functions with side effects and their governance mechanisms.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from diplomat_agent.models import Guard, SideEffect, Tool
from diplomat_agent.scanner.interprocedural import PackageIndex
from diplomat_agent.scanner.patterns import (
    EXCLUDED_DIRS,
    EXCLUDED_FILE_PATTERNS,
    GUARD_PATTERNS,
    ORCHESTRATOR_DECORATORS,
    READ_ONLY_PATTERNS,
    SIDE_EFFECT_PATTERNS,
)


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


def _matches_pattern(call: ast.Call, match: dict, source_lines: list[str]) -> bool:
    """Return True if an ast.Call node matches the given pattern match dict."""
    full_name, obj_name, attr_name = _call_parts(call)

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
    """Return True if a call matches any read-only pattern."""
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
        for pattern in SIDE_EFFECT_PATTERNS:
            if _matches_pattern(call=node, match=pattern["match"], source_lines=self.source_lines):
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
# Function analysis
# ---------------------------------------------------------------------------


def _analyze_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
    file_path: str,
    module_imports: set[str],
    package_index: "PackageIndex | None" = None,
) -> Tool | None:
    """Analyze a single function/method and return a Tool if it has side effects."""
    # --- Collect side effects (body only, skip decorators) ---
    se_visitor = _SideEffectVisitor(source_lines, file_path)
    for stmt in func_node.body:
        se_visitor.visit(stmt)
    side_effects = se_visitor.side_effects

    if not side_effects:
        return None

    # --- Filter out pure read-only functions ---
    # A function is read-only only if ALL its detected patterns are read-only.
    # We re-check: if side_effects contains only patterns that were also matched
    # by read-only patterns, skip. We do this by checking call nodes directly.
    write_effects = [se for se in side_effects if se.category != "read"]
    if not write_effects:
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

    # Combine, dedup by (type, line)
    all_guards: list[Guard] = []
    seen_guards: set[tuple[str, int]] = set()
    for g in dec_guards + imp_guards + dep_guards + body_guards:
        key = (g.type, g.line)
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

    return Tool(
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
    )


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------


def scan_file(file_path: Path, package_index: "PackageIndex | None" = None) -> list[Tool]:
    """Parse a single Python file and return all tools found."""
    source = file_path.read_text(encoding="utf-8", errors="replace")
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    module_imports = _collect_imports(tree)
    tools: list[Tool] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            tool = _analyze_function(
                func_node=node,
                source_lines=source_lines,
                file_path=str(file_path),
                module_imports=module_imports,
                package_index=package_index,
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
    is populated with ``files_scanned`` and ``files_skipped`` counts.
    """
    global last_scan_stats
    tools: list[Tool] = []
    files_scanned = 0
    files_skipped = 0

    package_index = PackageIndex(root)

    for py_file, included in _iter_all_python_files(root):
        if included:
            file_tools = scan_file(py_file, package_index=package_index)
            tools.extend(file_tools)
            files_scanned += 1
        else:
            files_skipped += 1

    last_scan_stats = {"files_scanned": files_scanned, "files_skipped": files_skipped}
    return tools


# Module-level stats populated by the last scan_directory() call
last_scan_stats: dict[str, int] = {"files_scanned": 0, "files_skipped": 0}


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
