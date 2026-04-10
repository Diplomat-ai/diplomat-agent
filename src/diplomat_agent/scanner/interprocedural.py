"""Inter-procedural decorator guard resolution (Phase 1: same-package only).

When a decorator is defined in another file within the same package the
scanner previously missed the guard entirely. This module resolves decorator
names to their definitions and inspects their bodies for guard patterns.
"""
from __future__ import annotations
import ast, logging
from pathlib import Path
from diplomat_agent.models import Guard

log = logging.getLogger(__name__)

_AUTH_RAISE_VOCAB: frozenset[str] = frozenset({
    "autherror","authorizationerror","authenticationerror","authfailed",
    "notauthenticated","unauthenticated","permissionerror","permissiondenied",
    "accessdenied","forbidden","unauthorized","httperror","httpexception","abort",
})
_AUTH_CONDITION_VOCAB: frozenset[str] = frozenset({
    "current_user","is_authenticated","is_authorized","has_permission",
    "is_logged_in","authenticated","authorized","verify_token",
    "check_permission","get_current_user",
})
_RATE_LIMIT_VOCAB: frozenset[str] = frozenset({
    "rate_limit","ratelimit","throttle","limiter","check_rate","is_limited","slowapi","limits",
})

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
            if _any_in(exc_name, _AUTH_RAISE_VOCAB):
                self.auth_evidence.append(ast.unparse(node.exc)[:80])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if _any_in(name, _AUTH_RAISE_VOCAB): self.auth_evidence.append(ast.unparse(node)[:80])
        if _any_in(name, _RATE_LIMIT_VOCAB): self.rate_limit_evidence.append(ast.unparse(node)[:80])
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        test_src = ast.unparse(node.test).lower()
        if any(token in test_src for token in _AUTH_CONDITION_VOCAB):
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
        guards.append(Guard(type="auth_check", evidence=f"@{dec_name} body ({source_label}): {a.auth_evidence[0]}", line=dec_def.lineno, coverage="full"))
    if a.rate_limit_evidence:
        guards.append(Guard(type="rate_limit", evidence=f"@{dec_name} body ({source_label}): {a.rate_limit_evidence[0]}", line=dec_def.lineno, coverage="full"))
    return guards


class PackageIndex:
    """Lazily parses same-package .py files to resolve decorator definitions."""
    def __init__(self, package_root: Path) -> None:
        self.root = package_root.resolve()
        self._defs: dict = {}
        self._imports: dict = {}

    def _load(self, file_path: Path) -> None:
        file_path = file_path.resolve()
        if file_path in self._defs: return
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"), filename=str(file_path))
        except (SyntaxError, OSError, ValueError) as e:
            log.debug("interprocedural: cannot parse %s: %s", file_path, e)
            self._defs[file_path] = {}; self._imports[file_path] = {}; return
        self._defs[file_path] = {n.name: n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                resolved = self._resolve_module(node.module, file_path)
                if resolved:
                    for alias in node.names:
                        imports[alias.asname or alias.name] = resolved
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_module(alias.name, file_path)
                    if resolved:
                        imports[alias.asname or alias.name.split(".")[0]] = resolved
        self._imports[file_path] = imports

    def _resolve_module(self, module_name: str, from_file: Path):
        candidate = self.root
        for part in module_name.lstrip(".").split("."): candidate = candidate / part
        f = candidate.with_suffix(".py")
        if f.exists(): return f.resolve()
        i = candidate / "__init__.py"
        if i.exists(): return i.resolve()
        return None

    def _lookup_def(self, name: str, from_file: Path):
        from_file = from_file.resolve(); self._load(from_file)
        imports = self._imports.get(from_file, {})
        if "." in name:
            mod, _, attr = name.rpartition(".")
            src = imports.get(mod)
            if src is None: return None, from_file
            self._load(src); return self._defs.get(src, {}).get(attr), src
        if name in imports:
            src = imports[name]; self._load(src); return self._defs.get(src, {}).get(name), src
        return self._defs.get(from_file, {}).get(name), from_file

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
