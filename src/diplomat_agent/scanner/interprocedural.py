"""Inter-procedural decorator guard resolution (Phase 1: same-package only).

When a decorator is defined in another file within the same package the
scanner previously missed the guard entirely. This module resolves decorator
names to their definitions and inspects their bodies for guard patterns.
"""
from __future__ import annotations
import ast, logging
from pathlib import Path
from diplomat_agent.models import Guard
from diplomat_agent.scanner.patterns import (
    INTER_PROC_AUTH_RAISE_VOCAB,
    INTER_PROC_AUTH_CONDITION_VOCAB,
    INTER_PROC_RATE_LIMIT_VOCAB,
)

log = logging.getLogger(__name__)

def _any_in(name: str, vocab: frozenset[str]) -> bool:
    low = name.lower()
    return any(token in low for token in vocab)

class _BodyAnalyser(ast.NodeVisitor):
    def __init__(self) -> None:
        self.auth_evidence: list[str] = []
        self.rate_limit_evidence: list[str] = []

    def visit_Raise(self, node: ast.Raise) -> None:
        if node.exc is not None:
            exc = node.exc
            if isinstance(exc, ast.Call): exc = exc.func
            exc_name = exc.id if isinstance(exc, ast.Name) else (exc.attr if isinstance(exc, ast.Attribute) else "")
            if _any_in(exc_name, INTER_PROC_AUTH_RAISE_VOCAB):
                self.auth_evidence.append(ast.unparse(node.exc)[:80])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if _any_in(name, INTER_PROC_AUTH_RAISE_VOCAB): self.auth_evidence.append(ast.unparse(node)[:80])
        if _any_in(name, INTER_PROC_RATE_LIMIT_VOCAB): self.rate_limit_evidence.append(ast.unparse(node)[:80])
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        test_src = ast.unparse(node.test).lower()
        if any(token in test_src for token in INTER_PROC_AUTH_CONDITION_VOCAB):
            for stmt in node.body:
                if isinstance(stmt, (ast.Raise, ast.Return, ast.Expr)):
                    self.auth_evidence.append(ast.unparse(node.test)[:80]); break
        self.generic_visit(node)

    def visit_FunctionDef(self, node): self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node): self.generic_visit(node)


def _guards_from_body(dec_def, dec_name: str, source_label: str) -> list[Guard]:
    a = _BodyAnalyser()
    for stmt in dec_def.body: a.visit(stmt)
    guards = []
    if a.auth_evidence:
        guards.append(Guard(type="auth_check", evidence=f"@{dec_name} body ({source_label}): {a.auth_evidence[0]}", line=dec_def.lineno, coverage="partial"))
    if a.rate_limit_evidence:
        guards.append(Guard(type="rate_limit", evidence=f"@{dec_name} body ({source_label}): {a.rate_limit_evidence[0]}", line=dec_def.lineno, coverage="partial"))
    return guards


class PackageIndex:
    """Lazily parses same-package .py files to resolve decorator definitions.

    Note: Class-level decorators (methods defined inside a class) are currently
    not indexed and will not be resolved by this index.
    """
    def __init__(self, package_root: Path) -> None:
        self.root = package_root.resolve()
        self._defs: dict = {}
        self._imports: dict = {}
        # FIX A v1 (v0.5.0) — memoization for inter-procedural side-effect /
        # guard resolution. Keyed by (callee_file_path_str, callee_funcname).
        # Value: tuple[list[SideEffect], list[Guard]] from the callee body
        # (already augmented with [via …] evidence and recursive descent).
        self._effects_cache: dict = {}
        # Lookup result cache: (name, from_file_str) → (def_or_None, resolved_file).
        # Caches both positive AND negative lookups so that repeated resolution
        # of stdlib/builtin names (len, str.format, list.append …) across
        # thousands of functions does not re-parse imports every time.
        self._lookup_cache: dict[tuple[str, str], tuple] = {}
        # Module resolve cache: (module_name, from_dir_str, level) → Path|None.
        # _resolve_module calls f.exists()+f.resolve() per module import —
        # caching avoids repeated filesystem round-trips for the same import.
        self._module_resolve_cache: dict[tuple[str, str, int], object] = {}
        # Path-key cache: str(path) → normcase(str(path.resolve())) string.
        # _lookup_def calls from_file.resolve() before the _lookup_cache check;
        # this ensures the expensive syscall is paid at most once per path string.
        self._path_key_cache: dict[str, str] = {}

    def _load(self, file_path: Path) -> None:
        # Normalise to a single canonical key: resolved + normcase.
        # We call resolve() once here and cache the result so that repeated
        # _load() calls for the same file are O(1) dict lookups after the
        # first visit. On Windows, Path.resolve() calls nt._getfinalpathname
        # which is the expensive syscall — we amortise it to one call per
        # distinct file rather than once per _lookup_def invocation.
        import os
        try:
            resolved = file_path.resolve()
        except (OSError, ValueError):
            resolved = file_path
        key = os.path.normcase(str(resolved))
        if key in self._defs:
            return
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"), filename=str(file_path))
        except (SyntaxError, OSError, ValueError) as e:
            log.debug("interprocedural: cannot parse %s: %s", file_path, e)
            self._defs[key] = {}; self._imports[key] = {}; return
        self._defs[key] = {n.name: n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                resolved_mod = self._resolve_module(node.module, file_path, level=node.level)
                if resolved_mod:
                    for alias in node.names:
                        imports[alias.asname or alias.name] = resolved_mod
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    resolved_mod = self._resolve_module(alias.name, file_path)
                    if resolved_mod:
                        imports[alias.asname or alias.name.split(".")[0]] = resolved_mod
        self._imports[key] = imports

    def _resolve_module(self, module_name: str, from_file: Path, level: int = 0):
        import os
        cache_key = (module_name, os.path.normcase(str(from_file.parent)), level)
        if cache_key in self._module_resolve_cache:
            return self._module_resolve_cache[cache_key]

        if level > 0:
            candidate = from_file.parent
            for _ in range(level - 1):
                candidate = candidate.parent
        else:
            candidate = self.root

        for part in module_name.split("."):
            candidate = candidate / part

        result = None
        f = candidate.with_suffix(".py")
        if f.exists():
            resolved = f.resolve()
            result = resolved if resolved.is_relative_to(self.root) else None
        else:
            i = candidate / "__init__.py"
            if i.exists():
                resolved = i.resolve()
                result = resolved if resolved.is_relative_to(self.root) else None
        self._module_resolve_cache[cache_key] = result
        return result

    def _path_key(self, p: Path) -> str:
        """Return normcase(str(p.resolve())), memoised per str(p) to avoid
        repeated nt._getfinalpathname syscalls on Windows."""
        import os
        p_str = str(p)
        k = self._path_key_cache.get(p_str)
        if k is None:
            try:
                k = os.path.normcase(str(p.resolve()))
            except (OSError, ValueError):
                k = os.path.normcase(p_str)
            self._path_key_cache[p_str] = k
        return k

    def _lookup_def(self, name: str, from_file: Path):
        from_key = self._path_key(from_file)
        cache_key = (name, from_key)
        if cache_key in self._lookup_cache:
            return self._lookup_cache[cache_key]
        self._load(from_file)
        imports = self._imports.get(from_key, {})
        if "." in name:
            mod, _, attr = name.rpartition(".")
            src = imports.get(mod)
            if src is None:
                result = (None, from_file)
                self._lookup_cache[cache_key] = result
                return result
            self._load(src)
            # src came from _resolve_module which already called f.resolve();
            # use _path_key to get the same normcase key without re-resolving.
            src_key = self._path_key(src)
            result = (self._defs.get(src_key, {}).get(attr), src)
            self._lookup_cache[cache_key] = result
            return result
        if name in imports:
            src = imports[name]; self._load(src)
            src_key = self._path_key(src)
            result = (self._defs.get(src_key, {}).get(name), src)
            self._lookup_cache[cache_key] = result
            return result
        result = (self._defs.get(from_key, {}).get(name), from_file)
        self._lookup_cache[cache_key] = result
        return result

    def resolve_decorator_guards(self, dec_node, from_file: Path) -> list[Guard]:
        node = dec_node.func if isinstance(dec_node, ast.Call) else dec_node
        if isinstance(node, ast.Name): dec_name = node.id
        elif isinstance(node, ast.Attribute): dec_name = ast.unparse(node)
        else: return []
        dec_def, source_file = self._lookup_def(dec_name, from_file)
        if dec_def is None: return []
        try: label = str(source_file.relative_to(self.root))
        except ValueError: label = source_file.name
        guards = _guards_from_body(dec_def, dec_name, label)
        if guards: log.debug("interprocedural: @%s in %s -> %d guard(s)", dec_name, from_file.name, len(guards))
        return guards
