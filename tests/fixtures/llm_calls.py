"""LLM calls via custom wrappers — should all be detected as effects."""


async def analyze_page(llm_api_handler, page_content: str):
    """Direct LLM call via custom handler."""
    result = await llm_api_handler(prompt=page_content, step="analyze")
    return result


async def process_with_app_handler(app):
    """LLM call via app-level handler."""
    result = await app.LLM_API_HANDLER(prompt="test", model="gpt-4")
    return result


async def run_agent(agent, state: dict):
    """Agent invoke — standard LangChain pattern."""
    result = await agent.ainvoke(state)
    return result


async def call_litellm(messages: list):
    """LiteLLM completion call."""
    import litellm
    result = await litellm.acompletion(model="gpt-4", messages=messages)
    return result


def format_llm_prompt(data: dict) -> str:
    """NOT an LLM call — just formatting. Should NOT appear in report."""
    return f"Analyze: {data}"


def parse_llm_response(response: str) -> dict:
    """NOT an LLM call — just parsing. Should NOT appear in report."""
    return {"parsed": response}
