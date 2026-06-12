"""Tests for false positive fixes and new pattern coverage."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diplomat_agent.scanner.ast_scanner import scan_file, scan_directory
from diplomat_agent.analyzer.guards import apply_verdicts


def _scan_code(code: str) -> list:
    tmpf = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False)
    tmpf.write(code)
    tmpf.close()
    try:
        return scan_file(Path(tmpf.name))
    finally:
        os.unlink(tmpf.name)


class TestRemoveFalsePositive:
    def test_remove_null_bytes_not_detected(self):
        """Standalone remove_null_bytes() must NOT trigger database_delete."""
        tools = _scan_code("""
def sanitize(data):
    result = remove_null_bytes(data)
    return result
""")
        assert len(tools) == 0

    def test_list_remove_not_detected(self):
        """list.remove() must NOT trigger database_delete."""
        tools = _scan_code("""
def clean_list(items, bad):
    items.remove(bad)
    return items
""")
        assert len(tools) == 0

    def test_collection_remove_still_detected(self):
        """collection.remove() SHOULD trigger database_delete (MongoDB)."""
        tools = _scan_code("""
def remove_doc(collection, doc_id):
    collection.remove({"_id": doc_id})
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_delete" in cats

    def test_os_remove_still_detected(self):
        """os.remove() SHOULD trigger file_delete."""
        tools = _scan_code("""
import os
def delete_file(path):
    os.remove(path)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "file_delete" in cats


class TestDecoratorFalsePositive:
    def test_router_delete_decorator_not_counted_as_effect(self):
        """@router.delete('/{id}') must NOT add side effects from decorator call."""
        tools = _scan_code("""
@router.delete("/{item_id}")
async def delete_item(item_id: str, db=None):
    db.delete(item_id)
    db.commit()
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        # Only body effects (db.delete, db.commit), NOT the decorator's route string
        assert "database_delete" in cats
        # Decorator call itself should NOT appear as http_write or similar
        assert "http_write" not in cats


class TestPublishFalsePositive:
    def test_published_at_not_detected(self):
        """published_at.isoformat() must NOT trigger publish."""
        tools = _scan_code("""
def get_article(article):
    date_str = article.published_at.isoformat()
    return {"published_at": date_str}
""")
        assert len(tools) == 0

    def test_is_published_not_detected(self):
        """obj.is_published() must NOT trigger publish."""
        tools = _scan_code("""
def check_status(article):
    return article.is_published()
""")
        assert len(tools) == 0

    def test_adapter_publish_still_detected(self):
        """adapter.publish(msg) SHOULD trigger publish."""
        tools = _scan_code("""
def send_event(adapter, msg):
    adapter.publish(msg)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "publish" in cats

    def test_standalone_publish_still_detected(self):
        """publish(msg) as standalone call SHOULD trigger publish."""
        tools = _scan_code("""
def emit(msg):
    publish(msg)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "publish" in cats


# ---------------------------------------------------------------------------
# Correction 2 — session.execute() read vs write
# ---------------------------------------------------------------------------


class TestExecuteReadVsWrite:
    def test_session_execute_text_select_not_detected(self):
        """session.execute(text('SELECT ...')) must NOT trigger database_write."""
        tools = _scan_code("""
def get_count(session):
    result = session.execute(text("SELECT count(*) FROM users"))
    return result.scalar()
""")
        assert len(tools) == 0

    def test_db_execute_select_func_not_detected(self):
        """db.execute(select(...)) must NOT trigger database_write."""
        tools = _scan_code("""
def get_users(db):
    result = db.execute(select(User).where(User.active == True))
    return result.scalars().all()
""")
        assert len(tools) == 0

    def test_session_execute_raw_select_not_detected(self):
        """session.execute('SELECT ...') raw string must NOT trigger database_write."""
        tools = _scan_code("""
def get_info(session):
    return session.execute("SELECT 1")
""")
        assert len(tools) == 0

    def test_session_execute_insert_detected(self):
        """session.execute(text('INSERT ...')) SHOULD trigger database_write."""
        tools = _scan_code("""
def add_user(session, name):
    session.execute(text("INSERT INTO users (name) VALUES (:name)"), {"name": name})
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_db_execute_insert_func_detected(self):
        """db.execute(insert(...)) SHOULD trigger database_write."""
        tools = _scan_code("""
def add_user(db, data):
    db.execute(insert(User).values(**data))
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_session_execute_update_text_detected(self):
        """session.execute(text('UPDATE ...')) SHOULD trigger database_write."""
        tools = _scan_code("""
def update_user(session, user_id, name):
    session.execute(text("UPDATE users SET name = :name WHERE id = :id"), {"name": name, "id": user_id})
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_session_execute_unknown_arg_detected(self):
        """session.execute(some_var) with unknown arg SHOULD trigger database_write (safe default)."""
        tools = _scan_code("""
def run_query(session, query):
    session.execute(query)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_cursor_execute_select_still_readonly(self):
        """cursor.execute('SELECT ...') existing read-only pattern must still work."""
        tools = _scan_code("""
def count_rows(cursor):
    cursor.execute("SELECT count(*) FROM users")
    return cursor.fetchone()
""")
        assert len(tools) == 0


# ---------------------------------------------------------------------------
# Correction 3 — Agent invocation patterns
# ---------------------------------------------------------------------------


class TestAgentInvocationPatterns:
    def test_graph_invoke_detected(self):
        """graph.invoke(state) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def run_pipeline(graph, state):
    result = graph.invoke(state)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_graph_ainvoke_detected(self):
        """graph.ainvoke(state) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
async def run_pipeline(graph, state):
    result = await graph.ainvoke(state)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_chain_invoke_detected(self):
        """chain.invoke(input) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def run_chain(chain, input_data):
    return chain.invoke(input_data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_brief_agent_analyze_detected(self):
        """brief_agent.analyze(data) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def analyze_brief(brief_agent, data):
    return brief_agent.analyze(data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_scraper_agent_execute_detected(self):
        """scraper_agent.execute(url) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def scrape(scraper_agent, url):
    return scraper_agent.execute(url)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_workflow_run_detected(self):
        """workflow.run(input) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def execute_workflow(workflow, data):
    return workflow.run(data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_agent_process_detected(self):
        """agent.process(data) SHOULD trigger agent_invocation."""
        tools = _scan_code("""
def run_agent(agent, data):
    return agent.process(data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "agent_invocation" in cats

    def test_regular_invoke_not_detected(self):
        """some_obj.invoke() on non-agent obj must NOT trigger agent_invocation."""
        tools = _scan_code("""
def call_func(callback):
    return callback.invoke()
""")
        assert len(tools) == 0

    def test_crew_kickoff_detected(self):
        code = textwrap.dedent("""\
            def run_crew():
                crew.kickoff()
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_crew_kickoff_async_detected(self):
        code = textwrap.dedent("""\
            async def run_crew():
                await crew.kickoff_async()
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_crew_kickoff_for_each_detected(self):
        code = textwrap.dedent("""\
            def run_crew(inputs):
                crew.kickoff_for_each(inputs=inputs)
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_autogen_initiate_chat_detected(self):
        code = textwrap.dedent("""\
            def run_autogen():
                assistant.initiate_chat(user_proxy, message="hello")
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_autogen_user_proxy_initiate_chat_detected(self):
        code = textwrap.dedent("""\
            def start():
                user_proxy.initiate_chat(assistant, message="start task")
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_compiled_graph_invoke_detected(self):
        """graph.compile().invoke(state) — standard LangGraph production pattern."""
        code = textwrap.dedent("""\
            def run():
                result = graph.compile().invoke(state)
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_app_invoke_detected(self):
        """app.invoke(state) — compiled graph stored in variable named 'app'."""
        code = textwrap.dedent("""\
            def run():
                app = graph.compile()
                result = app.invoke(state)
        """)
        tools = _scan_code(code)
        assert len(tools) == 1
        assert tools[0].side_effects[0].category == "agent_invocation"

    def test_flask_app_run_not_agent_invocation(self):
        """app.run() on Flask must NOT be detected as agent_invocation."""
        code = textwrap.dedent("""\
            def start_server():
                app.run(host='0.0.0.0', port=8080)
        """)
        tools = _scan_code(code)
        agent_inv = [t for t in tools if any(se.category == "agent_invocation" for se in t.side_effects)]
        assert len(agent_inv) == 0, "Flask app.run() must not be flagged as agent_invocation"

    def test_subprocess_run_not_agent(self):
        """subprocess.run() must NOT trigger agent_invocation (already destructive)."""
        tools = _scan_code("""
import subprocess
def run_cmd(cmd):
    subprocess.run(cmd)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats
        assert "agent_invocation" not in cats


# ---------------------------------------------------------------------------
# Correction 4 — Repository CRUD patterns
# ---------------------------------------------------------------------------


class TestRepositoryPatterns:
    def test_repo_create_detected(self):
        """workflow_repo.create(data) SHOULD trigger database_write."""
        tools = _scan_code("""
def save_via_repo(workflow_repo, data):
    result = workflow_repo.create(data)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_constructor_repo_create_detected(self):
        """WorkflowExecutionRepository(session).create(data) SHOULD trigger database_write."""
        tools = _scan_code("""
def save_via_constructor(session, data):
    result = WorkflowExecutionRepository(session).create(data)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_self_repo_create_detected(self):
        """self.repo.create(data) SHOULD trigger database_write."""
        tools = _scan_code("""
class Service:
    def save(self, data):
        return self.repo.create(data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_repo_delete_detected(self):
        """workflow_repo.delete(id) SHOULD trigger database_delete."""
        tools = _scan_code("""
def delete_via_repo(workflow_repo, record_id):
    workflow_repo.delete(record_id)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_delete" in cats

    def test_dao_update_detected(self):
        """user_dao.update(data) SHOULD trigger database_write."""
        tools = _scan_code("""
def update_user(user_dao, data):
    user_dao.update(data)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats

    def test_store_save_detected(self):
        """data_store.save(item) SHOULD trigger database_write."""
        tools = _scan_code("""
def persist(data_store, item):
    data_store.save(item)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_write" in cats


# ---------------------------------------------------------------------------
# Correction 5 — Fixture integration tests
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


class TestFalsePositiveFixture:
    """Functions in false_positives.py must NOT be detected as tools."""

    def setup_method(self):
        tools = scan_file(FIXTURES / "false_positives.py")
        self.tool_names = {t.name for t in tools}

    def test_clean_data_not_detected(self):
        assert "clean_data" not in self.tool_names

    def test_check_health_not_detected(self):
        assert "check_health" not in self.tool_names

    def test_get_publication_date_not_detected(self):
        assert "get_publication_date" not in self.tool_names

    def test_list_items_not_detected(self):
        assert "list_items" not in self.tool_names

    def test_format_name_not_detected(self):
        assert "format_name" not in self.tool_names


class TestAgentCallsFixture:
    """Functions in agent_calls.py MUST be detected with correct categories."""

    def setup_method(self):
        tools = scan_file(FIXTURES / "agent_calls.py")
        self.tools = {t.name: t for t in tools}

    def test_analyze_brief_detected(self):
        assert "analyze_brief" in self.tools

    def test_analyze_brief_is_agent_invocation(self):
        cats = {se.category for se in self.tools["analyze_brief"].side_effects}
        assert "agent_invocation" in cats

    def test_run_generation_detected(self):
        assert "run_generation" in self.tools

    def test_run_generation_is_agent_invocation(self):
        cats = {se.category for se in self.tools["run_generation"].side_effects}
        assert "agent_invocation" in cats

    def test_scrape_and_analyze_detected(self):
        assert "scrape_and_analyze" in self.tools

    def test_scrape_and_analyze_is_agent_invocation(self):
        cats = {se.category for se in self.tools["scrape_and_analyze"].side_effects}
        assert "agent_invocation" in cats

    def test_save_via_repo_detected(self):
        assert "save_via_repo" in self.tools

    def test_save_via_repo_is_database_write(self):
        cats = {se.category for se in self.tools["save_via_repo"].side_effects}
        assert "database_write" in cats

    def test_save_via_constructor_detected(self):
        assert "save_via_constructor" in self.tools

    def test_save_via_constructor_is_database_write(self):
        cats = {se.category for se in self.tools["save_via_constructor"].side_effects}
        assert "database_write" in cats

    def test_delete_via_repo_detected(self):
        assert "delete_via_repo" in self.tools

    def test_delete_via_repo_is_database_delete(self):
        cats = {se.category for se in self.tools["delete_via_repo"].side_effects}
        assert "database_delete" in cats

    def test_run_chain_detected(self):
        assert "run_chain" in self.tools

    def test_run_chain_is_agent_invocation(self):
        cats = {se.category for se in self.tools["run_chain"].side_effects}
        assert "agent_invocation" in cats


# ---------------------------------------------------------------------------
# Short substring false positives (ses, bot, p)
# ---------------------------------------------------------------------------


class TestShortSubstringFalsePositives:
    """Objects with 'session' in the name must NOT trigger email (ses pattern)."""

    def test_cdp_session_send_not_email(self):
        """cdp_session.send() must NOT trigger email."""
        tools = _scan_code("""
async def handle_cdp(cdp_session):
    await cdp_session.send("Page.navigate", {"url": "https://example.com"})
""")
        for t in tools:
            cats = {se.category for se in t.side_effects}
            assert "email" not in cats

    def test_browser_session_close_not_email(self):
        """browser_session.close() must NOT trigger email."""
        tools = _scan_code("""
async def close_browser(browser_session):
    await browser_session.close()
""")
        for t in tools:
            cats = {se.category for se in t.side_effects}
            assert "email" not in cats

    def test_persistent_sessions_manager_not_email(self):
        """persistent_sessions_manager.clear() must NOT trigger email."""
        tools = _scan_code("""
async def cleanup(persistent_sessions_manager):
    await persistent_sessions_manager.clear()
""")
        assert len(tools) == 0

    def test_robot_send_not_email(self):
        """robot.send() must NOT trigger email (was matched by 'bot' substring)."""
        tools = _scan_code("""
def handler(robot):
    robot.send("status")
""")
        for t in tools:
            cats = {se.category for se in t.side_effects}
            assert "email" not in cats

    def test_bare_ses_still_detected(self):
        """ses.send_email() SHOULD still trigger email (exact match)."""
        tools = _scan_code("""
def send_ses_email(ses, to, body):
    ses.send_email(Source="noreply@example.com", Destination={"ToAddresses": [to]})
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "email" in cats

    def test_ses_client_still_detected(self):
        """ses_client.send_email() SHOULD still trigger email."""
        tools = _scan_code("""
def send_via_ses(ses_client, to, body):
    ses_client.send_email(Source="noreply@example.com", Destination={"ToAddresses": [to]})
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "email" in cats


class TestShortSubstringFixture:
    """Scan false_positives_short_substring.py — zero email findings."""

    def setup_method(self):
        tools = scan_file(FIXTURES / "false_positives_short_substring.py")
        self.tools = {t.name: t for t in tools}

    def test_no_email_findings(self):
        for name, tool in self.tools.items():
            cats = {se.category for se in tool.side_effects}
            assert "email" not in cats, f"{name} was incorrectly flagged as email"


# ---------------------------------------------------------------------------
# Depends() auth guard detection
# ---------------------------------------------------------------------------


class TestDependsAuthGuard:
    """Depends(get_current_org) in function signature must be detected as auth_check."""

    def test_depends_detected_as_auth_check(self):
        """Depends(func) in default param SHOULD produce auth_check guard."""
        tools = _scan_code("""
async def delete_workflow(workflow_id: str, org=Depends(get_current_org)):
    await db.delete(workflow_id)
    await db.commit()
""")
        assert len(tools) == 1
        guard_types = {g.type for g in tools[0].guards}
        assert "auth_check" in guard_types

    def test_depends_kwonly_detected(self):
        """Depends() in keyword-only arg should also work."""
        tools = _scan_code("""
async def create_task(data: dict, *, org=Depends(get_current_org)):
    db.add(data)
    await db.commit()
""")
        assert len(tools) == 1
        guard_types = {g.type for g in tools[0].guards}
        assert "auth_check" in guard_types

    def test_no_depends_no_auth_guard(self):
        """Function without Depends() should NOT get auth_check from params."""
        tools = _scan_code("""
async def create_no_auth(data: dict):
    db.add(data)
    await db.commit()
""")
        assert len(tools) == 1
        guard_types = {g.type for g in tools[0].guards}
        assert "auth_check" not in guard_types

    def test_depends_evidence_contains_function_name(self):
        """Guard evidence should mention what's inside Depends()."""
        tools = _scan_code("""
async def update_item(item_id: str, org=Depends(get_current_org)):
    db.add(item_id)
    await db.commit()
""")
        assert len(tools) == 1
        auth_guards = [g for g in tools[0].guards if g.type == "auth_check"]
        assert len(auth_guards) >= 1
        assert "get_current_org" in auth_guards[0].evidence

    def test_security_detected_as_auth_check(self):
        """Security(scheme) in function signature must produce auth_check guard."""
        tools = _scan_code("""
async def protected(credentials=Security(http_bearer)):
    db.add('x')
    await db.commit()
""")
        assert len(tools) == 1
        guard_types = {g.type for g in tools[0].guards}
        assert "auth_check" in guard_types

    def test_security_evidence_mentions_security(self):
        """Guard evidence for Security() should say Security(...)."""
        tools = _scan_code("""
async def protected(credentials=Security(http_bearer)):
    db.add('x')
    await db.commit()
""")
        auth_guards = [g for g in tools[0].guards if g.type == "auth_check"]
        assert auth_guards[0].evidence.startswith("Security(")


class TestDependsFixtureVerdicts:
    """Fixture-based test: verdicts with Depends() auth."""

    def setup_method(self):
        tools = scan_file(FIXTURES / "fastapi_depends.py")
        apply_verdicts(tools)
        self.tools = {t.name: t for t in tools}

    def test_delete_workflow_has_auth(self):
        assert "delete_workflow" in self.tools
        guard_types = {g.type for g in self.tools["delete_workflow"].guards}
        assert "auth_check" in guard_types

    def test_delete_workflow_partially_guarded(self):
        assert self.tools["delete_workflow"].verdict == "PARTIALLY_GUARDED"

    def test_create_task_has_auth(self):
        assert "create_task" in self.tools
        guard_types = {g.type for g in self.tools["create_task"].guards}
        assert "auth_check" in guard_types

    def test_create_task_partially_guarded(self):
        assert self.tools["create_task"].verdict == "PARTIALLY_GUARDED"

    def test_create_without_auth_unguarded(self):
        assert "create_without_auth" in self.tools
        assert self.tools["create_without_auth"].verdict == "UNGUARDED"

    def test_security_route_has_auth_guard(self):
        assert "protected_route" in self.tools
        guard_types = {g.type for g in self.tools["protected_route"].guards}
        assert "auth_check" in guard_types

    def test_security_route_partially_guarded(self):
        assert self.tools["protected_route"].verdict == "PARTIALLY_GUARDED"


# ---------------------------------------------------------------------------
# LLM call detection
# ---------------------------------------------------------------------------


class TestLLMCallPatterns:
    """LLM calls via custom wrappers must be detected as llm_call effects."""

    def test_direct_llm_api_handler(self):
        """Direct function call: llm_api_handler(prompt=...)."""
        tools = _scan_code("""
async def analyze(llm_api_handler, content):
    result = await llm_api_handler(prompt=content)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_app_level_handler(self):
        """Attribute call: app.LLM_API_HANDLER(...)."""
        tools = _scan_code("""
async def process(app):
    result = await app.LLM_API_HANDLER(prompt="test")
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_litellm_acompletion(self):
        """litellm.acompletion() must be detected."""
        tools = _scan_code("""
async def call_litellm(messages):
    import litellm
    result = await litellm.acompletion(model="gpt-4", messages=messages)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_openai_chat_completions(self):
        """OpenAI chat.completions.create() detected."""
        tools = _scan_code("""
async def ask_openai(client, prompt):
    result = await client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": prompt}])
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_llm_object_invoke(self):
        """llm.invoke() / model.ainvoke() detected as llm_call."""
        tools = _scan_code("""
async def run_llm(llm, prompt):
    result = await llm.ainvoke(prompt)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_format_llm_prompt_not_detected(self):
        """format_llm_prompt() is read-only — must NOT be detected."""
        tools = _scan_code("""
def format_llm_prompt(data):
    return f"Analyze: {data}"
""")
        assert len(tools) == 0

    def test_parse_llm_response_not_detected(self):
        """parse_llm_response() is read-only — must NOT be detected."""
        tools = _scan_code("""
def parse_llm_response(response):
    return {"parsed": response}
""")
        assert len(tools) == 0

    def test_call_llm_wrapper(self):
        """call_llm(...) custom wrapper detected."""
        tools = _scan_code("""
async def do_work(prompt):
    result = await call_llm(prompt=prompt)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats

    def test_get_llm_response_wrapper(self):
        """get_llm_response(...) custom wrapper detected."""
        tools = _scan_code("""
async def do_work(prompt):
    result = await get_llm_response(prompt)
    return result
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "llm_call" in cats


class TestLLMCallsFixture:
    """Fixture-based: scan llm_calls.py and verify expected detections."""

    def setup_method(self):
        tools = scan_file(FIXTURES / "llm_calls.py")
        self.tools = {t.name: t for t in tools}

    def test_analyze_page_detected(self):
        assert "analyze_page" in self.tools
        cats = {se.category for se in self.tools["analyze_page"].side_effects}
        assert "llm_call" in cats

    def test_process_with_app_handler_detected(self):
        assert "process_with_app_handler" in self.tools
        cats = {se.category for se in self.tools["process_with_app_handler"].side_effects}
        assert "llm_call" in cats

    def test_run_agent_detected(self):
        assert "run_agent" in self.tools
        cats = {se.category for se in self.tools["run_agent"].side_effects}
        assert "agent_invocation" in cats

    def test_call_litellm_detected(self):
        assert "call_litellm" in self.tools
        cats = {se.category for se in self.tools["call_litellm"].side_effects}
        assert "llm_call" in cats

    def test_format_llm_prompt_not_detected(self):
        assert "format_llm_prompt" not in self.tools

    def test_parse_llm_response_not_detected(self):
        assert "parse_llm_response" not in self.tools


# ---------------------------------------------------------------------------
# Correction 1 — "drop" substring false positives
# ---------------------------------------------------------------------------


class TestDropSubstringFalsePositives:
    """drop_duplicates, dropna, _drop_dashes must NOT be flagged."""

    def test_drop_dashes_helper_not_detected(self):
        tools = _scan_code("""
def _drop_dashes(text: str) -> str:
    return text.replace("-", "")
""")
        assert len(tools) == 0

    def test_drop_duplicates_pandas_not_detected(self):
        tools = _scan_code("""
def clean(df):
    return df.drop_duplicates()
""")
        assert len(tools) == 0

    def test_dropna_pandas_not_detected(self):
        tools = _scan_code("""
def clean(df):
    return df.dropna()
""")
        assert len(tools) == 0

    def test_db_drop_still_detected(self):
        """db.drop() has DB-context obj — must still be detected."""
        tools = _scan_code("""
def reset_db(db):
    db.drop()
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_delete" in cats

    def test_metadata_drop_all_still_detected(self):
        """SQLAlchemy metadata.drop_all() must still be detected."""
        tools = _scan_code("""
def teardown(metadata):
    metadata.drop_all()
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_delete" in cats

    def test_collection_drop_still_detected(self):
        """MongoDB collection.drop() must still be detected."""
        tools = _scan_code("""
def reset_collection(collection):
    collection.drop()
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "database_delete" in cats


class TestDropFixture:
    """Fixture scan — the drop FP file must produce zero findings."""

    def setup_method(self):
        self.tools = {t.name: t for t in scan_file(FIXTURES / "false_positives_drop.py")}

    def test_drop_dashes_not_in_report(self):
        assert "_drop_dashes" not in self.tools

    def test_clean_dataframe_not_in_report(self):
        assert "clean_dataframe" not in self.tools

    def test_fetch_data_not_in_report(self):
        assert "fetch_data" not in self.tools


# ---------------------------------------------------------------------------
# Correction 2 — importlib / exec / eval as destructive effects
# ---------------------------------------------------------------------------


class TestDynamicCodePatterns:
    """exec, eval, __import__, importlib.import_module must be detected."""

    def test_exec_detected(self):
        tools = _scan_code("""
def run_code(code: str):
    exec(code)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_eval_detected(self):
        tools = _scan_code("""
def evaluate(expr: str):
    return eval(expr)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_importlib_import_module_detected(self):
        tools = _scan_code("""
def load(module_path: str):
    import importlib
    return importlib.import_module(module_path)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_dunder_import_detected(self):
        tools = _scan_code("""
def load(name: str):
    return __import__(name)
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        assert "destructive" in cats

    def test_cursor_execute_not_matched(self):
        """cursor.execute() must NOT match the exec builtin pattern."""
        tools = _scan_code("""
def insert_row(cursor):
    cursor.execute("INSERT INTO logs VALUES (1)")
""")
        assert len(tools) == 1
        cats = {se.category for se in tools[0].side_effects}
        # Should be database_write, not 'destructive' via exec pattern
        assert "destructive" not in cats
        assert "database_write" in cats

    def test_ast_literal_eval_not_matched(self):
        """ast.literal_eval() must NOT match the eval builtin pattern."""
        tools = _scan_code("""
def parse(s: str):
    import ast
    return ast.literal_eval(s)
""")
        assert len(tools) == 0


class TestDynamicCodeFixture:
    """Fixture-based tests for dynamic code detection."""

    def setup_method(self):
        self.tools = {t.name: t for t in scan_file(FIXTURES / "dynamic_code.py")}

    def test_load_strategy_detected(self):
        assert "load_strategy" in self.tools
        cats = {se.category for se in self.tools["load_strategy"].side_effects}
        assert "destructive" in cats

    def test_execute_generated_code_detected(self):
        assert "execute_generated_code" in self.tools
        cats = {se.category for se in self.tools["execute_generated_code"].side_effects}
        assert "destructive" in cats

    def test_evaluate_expression_detected(self):
        assert "evaluate_expression" in self.tools
        cats = {se.category for se in self.tools["evaluate_expression"].side_effects}
        assert "destructive" in cats

    def test_safe_import_detected(self):
        """Even static-arg importlib.import_module must be detected."""
        assert "safe_import" in self.tools
        cats = {se.category for se in self.tools["safe_import"].side_effects}
        assert "destructive" in cats


class TestOpenAIAgentsSDK:
    """Tests for OpenAI Agents SDK Runner.run_sync detection."""

    @classmethod
    def setup_class(cls):
        code = textwrap.dedent("""\
            from agents import Agent, Runner

            def run_openai_agent(user_input: str):
                agent = Agent(name="assistant", instructions="You help users.")
                result = Runner.run_sync(agent, user_input)
                return result
        """)
        cls.tools = {t.name: t for t in _scan_code(code)}

    def test_runner_run_sync_detected(self):
        """Runner.run_sync must be detected as agent_invocation."""
        assert "run_openai_agent" in self.tools
        tool = self.tools["run_openai_agent"]
        cats = {se.category for se in tool.side_effects}
        assert "agent_invocation" in cats

    def test_runner_run_sync_unguarded(self):
        """Runner.run_sync with no checks must be UNGUARDED."""
        tool = self.tools["run_openai_agent"]
        apply_verdicts([tool])
        assert tool.verdict == "UNGUARDED"


class TestSetTransactionNotDbWrite:
    """FP1 — conn.execute('SET TRANSACTION READ ONLY') must not be flagged as database_write."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "fp_set_transaction_readonly.py"
        cls.tools = {t.name: t for t in scan_file(fixture)}

    def test_set_transaction_not_db_write(self):
        """SET TRANSACTION READ ONLY is a transaction-mode statement, not a mutation.

        run_write has a real INSERT (must be found) and a SET TRANSACTION (must NOT
        add an extra database_write side effect).  Exactly 1 database_write expected.
        """
        assert "run_write" in self.tools, "fixture function run_write not scanned"
        tool = self.tools["run_write"]
        db_write_effects = [se for se in tool.side_effects if se.category == "database_write"]
        set_tx_effects = [
            se for se in db_write_effects if "SET TRANSACTION" in se.evidence.upper()
        ]
        assert set_tx_effects == [], (
            f"SET TRANSACTION was incorrectly flagged as database_write: {set_tx_effects}"
        )
        # The real INSERT must still be detected (exactly 1 db_write)
        assert len(db_write_effects) == 1, (
            f"Expected exactly 1 database_write (the INSERT), got {len(db_write_effects)}: "
            f"{[se.evidence for se in db_write_effects]}"
        )

    def test_pure_read_query_no_findings(self):
        """run_query (SET TRANSACTION + fetch only) must produce no findings at all."""
        assert "run_query" not in self.tools, (
            "run_query has no writes — scan_file must return no Tool for it; "
            f"got side_effects={[se.evidence for se in self.tools.get('run_query', type('T',[],{'side_effects':[]})()).side_effects]}"
        )


# ---------------------------------------------------------------------------
# GATE 1 — benign stdlib method calls must NOT be OPAQUE
# ---------------------------------------------------------------------------


class TestBenignStdlibNotOpaque:
    """GATE 1: @mcp.tool that only calls stdlib methods on typed params (str,
    dict, list) must NOT be classified as OPAQUE."""

    @classmethod
    def setup_class(cls):
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        fixture = Path(__file__).parent / "fixtures" / "mcp" / "benign_typed_call.py"
        tools = scan_file(fixture)
        apply_verdicts(tools)
        cls.tools = {t.name: t for t in tools}

    def test_benign_stdlib_not_opaque(self):
        """fmt() with only s.upper(), d.get(), items[:2] must not be OPAQUE."""
        if "fmt" in self.tools:
            assert self.tools["fmt"].verdict != "OPAQUE", (
                f"fmt() was incorrectly classified as OPAQUE; "
                f"opaque_reason={self.tools['fmt'].opaque_reason!r}"
            )

    def test_wrapped_db_still_opaque(self):
        """Regression: wrapped_db_tool.run_query must still be OPAQUE."""
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        fixture = Path(__file__).parent / "fixtures" / "mcp" / "wrapped_db_tool.py"
        tools = scan_file(fixture)
        apply_verdicts(tools)
        tools_by_name = {t.name: t for t in tools}
        assert "run_query" in tools_by_name
        assert tools_by_name["run_query"].verdict == "OPAQUE", (
            f"wrapped_db_tool.run_query must still be OPAQUE after the fix; "
            f"got {tools_by_name['run_query'].verdict!r}"
        )

    def test_wrapped_socket_still_opaque(self):
        """Regression: wrapped_socket_tool.do_thing must still be OPAQUE."""
        from pathlib import Path
        from diplomat_agent.scanner.ast_scanner import scan_file
        from diplomat_agent.analyzer.guards import apply_verdicts
        fixture = Path(__file__).parent / "fixtures" / "mcp" / "wrapped_socket_tool.py"
        tools = scan_file(fixture)
        apply_verdicts(tools)
        tools_by_name = {t.name: t for t in tools}
        assert "do_thing" in tools_by_name
        assert tools_by_name["do_thing"].verdict == "OPAQUE", (
            f"wrapped_socket_tool.do_thing must still be OPAQUE after the fix; "
            f"got {tools_by_name['do_thing'].verdict!r}"
        )


# ---------------------------------------------------------------------------
# PHASE 1 — Ambiguous mutator names: untyped receiver must be OPAQUE
# ---------------------------------------------------------------------------


class TestUntypedMutatorIsOpaque:
    """Phase 1 locking test: ambiguous mutator method on untyped receiver must
    trigger OPAQUE, not be silently dropped. Builtin-typed receiver must be clean."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "mcp" / "untyped_mutator.py"
        tools = scan_file(fixture)
        apply_verdicts(tools)
        cls.tools = {t.name: t for t in tools}

    def test_write_cache_is_opaque(self):
        """cache.add(k, v) with untyped cache must be OPAQUE — unknown effect surface."""
        assert "write_cache" in self.tools, (
            f"write_cache not found; got {list(self.tools)}"
        )
        assert self.tools["write_cache"].verdict == "OPAQUE", (
            f"write_cache must be OPAQUE (cache is untyped, .add is ambiguous); "
            f"got verdict={self.tools['write_cache'].verdict!r}, "
            f"opaque_reason={self.tools['write_cache'].opaque_reason!r}"
        )

    def test_append_list_is_clean(self):
        """items.append(x) with items:list (builtin typed) must NOT be OPAQUE."""
        if "append_list" in self.tools:
            assert self.tools["append_list"].verdict != "OPAQUE", (
                f"append_list must not be OPAQUE (items is typed list, append is in-memory); "
                f"got {self.tools['append_list'].verdict!r}"
            )


# ---------------------------------------------------------------------------
# PHASE 4 — sleep is never an external side effect
# ---------------------------------------------------------------------------


class TestSleepNotOpaque:
    """asyncio.sleep / time.sleep / trio.sleep are wait primitives, never
    external side effects. They must not push a tool to OPAQUE."""

    @classmethod
    def setup_class(cls):
        fixture = Path(__file__).parent / "fixtures" / "mcp" / "benign_sleep.py"
        tools = scan_file(fixture)
        apply_verdicts(tools)
        cls.tools = {t.name: t for t in tools}

    def test_sleep_not_opaque(self):
        """waits() uses only asyncio.sleep + time.sleep — must NOT be OPAQUE,
        and ideally must produce no Tool entry at all (no findings)."""
        if "waits" in self.tools:
            verdict = self.tools["waits"].verdict
            reason = self.tools["waits"].opaque_reason
            assert verdict != "OPAQUE", (
                f"waits() must not be OPAQUE — only sleep calls, no external effect; "
                f"got verdict={verdict!r}, opaque_reason={reason!r}"
            )
