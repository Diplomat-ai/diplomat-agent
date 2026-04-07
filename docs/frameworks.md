# Supported frameworks

> Back to [README](../README.md)

| Framework | Coverage | Unguarded % (benchmarks) |
|---|---|---|
| LangGraph | StateGraph, tool nodes, conditional edges | 76% (Skyvern) |
| CrewAI | @tool decorator, agent.execute() | 78% |
| OpenAI SDK | client.chat.completions.create(), function_call | — |
| OpenAI Agents SDK | @function_tool, Runner patterns | — |
| LangChain | @tool, BaseTool, AgentExecutor | — |
| Direct API calls | requests, httpx, aiohttp, urllib | 75% (Dify) |
