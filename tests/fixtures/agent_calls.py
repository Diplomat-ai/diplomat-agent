"""Agent and repository fixture — these functions MUST be detected as side effects."""


async def analyze_brief(brief_agent, data: dict):
    """Agent LLM call - effect coûteux."""
    result = await brief_agent.analyze(data)
    return result


async def run_generation(graph, state: dict):
    """Graph invoke - pipeline LLM complet."""
    result = await graph.ainvoke(state)
    return result


async def scrape_and_analyze(scraper_agent, url: str):
    """Agent execute - scraping + LLM."""
    result = await scraper_agent.execute(url)
    return result


async def save_via_repo(workflow_repo, data: dict):
    """Repository create - write DB indirect."""
    result = await workflow_repo.create(data)
    return result


async def save_via_constructor(session, data: dict):
    """Constructor-based repository create."""
    result = await WorkflowExecutionRepository(session).create(data)
    return result


async def delete_via_repo(workflow_repo, record_id: str):
    """Repository delete - DB delete indirect."""
    await workflow_repo.delete(record_id)


async def run_chain(chain, input_data: dict):
    """LangChain chain invoke."""
    return await chain.invoke(input_data)
