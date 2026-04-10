"""Tests for inter-procedural decorator guard resolution."""
from __future__ import annotations
import ast, sys, textwrap
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from diplomat_agent.scanner.interprocedural import PackageIndex, _BodyAnalyser, _guards_from_body
from diplomat_agent.scanner.ast_scanner import scan_directory, scan_file
from diplomat_agent.analyzer.guards import apply_verdicts

FIXTURES = Path(__file__).parent / "fixtures" / "interprocedural"

def _pf(source):
    tree = ast.parse(textwrap.dedent(source))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): return n

def _scan():
    tools = scan_directory(FIXTURES); apply_verdicts(tools)
    return {t.name: t for t in tools}

class TestBodyAnalyser:
    def _analyse(self, source):
        f = _pf(source); a = _BodyAnalyser()
        for s in f.body: a.visit(s)
        return a
    def test_raise_autherror(self):
        a = self._analyse("""
            def d(fn):
                def w(*a,**k):
                    if not current_user: raise AuthError("x")
                    return fn(*a,**k)
                return w""")
        assert a.auth_evidence
    def test_abort_call(self):
        a = self._analyse("""
            def d(fn):
                def w(*a,**k):
                    if not current_user.is_authenticated: abort(403)
                    return fn(*a,**k)
                return w""")
        assert a.auth_evidence
    def test_rate_limit(self):
        a = self._analyse("""
            def d(fn):
                def w(*a,**k): check_rate_limit(current_user); return fn(*a,**k)
                return w""")
        assert a.rate_limit_evidence
    def test_no_fp_logging(self):
        a = self._analyse("""
            def d(fn):
                def w(*a,**k): print("hi"); return fn(*a,**k)
                return w""")
        assert not a.auth_evidence and not a.rate_limit_evidence
    def test_no_fp_cache(self):
        a = self._analyse("""
            def d(fn):
                c={}
                def w(*a,**k):
                    if str(a) not in c: c[str(a)]=fn(*a,**k)
                    return c[str(a)]
                return w""")
        assert not a.auth_evidence and not a.rate_limit_evidence

class TestGuardsFromBody:
    def _f(self):
        return _pf("""
            def require_policy(fn):
                def w(*a,**k):
                    if not current_user: raise AuthError("x")
                    return fn(*a,**k)
                return w""")
    def test_returns_auth_guard(self):
        assert any(g.type=="auth_check" for g in _guards_from_body(self._f(),"require_policy","middleware.py"))
    def test_full_coverage(self):
        assert all(g.coverage=="full" for g in _guards_from_body(self._f(),"require_policy","middleware.py") if g.type=="auth_check")
    def test_evidence_has_name(self):
        assert any("require_policy" in g.evidence for g in _guards_from_body(self._f(),"require_policy","middleware.py"))
    def test_evidence_has_source(self):
        assert any("middleware.py" in g.evidence for g in _guards_from_body(self._f(),"require_policy","middleware.py"))
    def test_pure_decorator_no_guards(self):
        f = _pf("""
            def log_calls(fn):
                def w(*a,**k): print("x"); return fn(*a,**k)
                return w""")
        assert _guards_from_body(f,"log_calls","middleware.py") == []

class TestPackageIndex:
    def setup_method(self): self.idx = PackageIndex(FIXTURES)
    def _dec(self, fn):
        tree = ast.parse((FIXTURES/"tools.py").read_text())
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==fn:
                return n.decorator_list[0]
    def test_resolves_require_policy(self):
        assert self.idx.resolve_decorator_guards(self._dec("delete_record"), FIXTURES/"tools.py")
    def test_type_is_auth_check(self):
        assert any(g.type=="auth_check" for g in self.idx.resolve_decorator_guards(self._dec("delete_record"), FIXTURES/"tools.py"))
    def test_log_calls_no_guards(self):
        assert self.idx.resolve_decorator_guards(self._dec("unguarded_write"), FIXTURES/"tools.py") == []
    def test_idempotent(self):
        d,f = self._dec("delete_record"), FIXTURES/"tools.py"
        assert len(self.idx.resolve_decorator_guards(d,f)) == len(self.idx.resolve_decorator_guards(d,f))
    def test_third_party_no_raise(self):
        tree = ast.parse("import celery\n@celery.task\ndef f(): pass")
        for n in ast.walk(tree):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                assert isinstance(self.idx.resolve_decorator_guards(n.decorator_list[0], FIXTURES/"tools.py"), list); return

class TestIntegration:
    def setup_method(self): self.tools = _scan()
    def test_delete_record_detected(self): assert "delete_record" in self.tools
    def test_delete_record_has_auth(self): assert "auth_check" in {g.type for g in self.tools["delete_record"].guards}
    def test_delete_record_not_unguarded(self): assert self.tools["delete_record"].verdict != "UNGUARDED"
    def test_update_record_has_auth(self): assert "auth_check" in {g.type for g in self.tools["update_record"].guards}
    def test_purge_user_has_auth(self): assert "auth_check" in {g.type for g in self.tools["purge_user"].guards}
    def test_send_admin_email_has_auth(self): assert "auth_check" in {g.type for g in self.tools["send_admin_email"].guards}
    def test_bulk_write_has_rate_limit(self): assert "rate_limit" in {g.type for g in self.tools["bulk_write"].guards}
    def test_unguarded_write_stays_unguarded(self):
        t = self.tools["unguarded_write"]
        assert "auth_check" not in {g.type for g in t.guards}
        assert t.verdict == "UNGUARDED"
    def test_scan_file_standalone_works(self): assert isinstance(scan_file(FIXTURES/"tools.py"), list)
    def test_scan_file_finds_side_effects(self): assert any(t.name=="delete_record" for t in scan_file(FIXTURES/"tools.py"))
