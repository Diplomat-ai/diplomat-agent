# Methodology

## Data source

We analyzed GitHub issues from 6 major agentic AI repositories:

- `langchain-ai/langgraph` (169 collected, 148 relevant)
- `crewAIInc/crewAI` (207 collected, 146 relevant)
- `microsoft/autogen` (91 collected, 71 relevant)
- `openai/openai-agents-python` (248 collected, 189 relevant)
- `anthropics/claude-code` (1,792 collected, 1,450 relevant)
- `vercel/ai` (540 collected, 328 relevant)

## Collection

3,047 issues collected via the GitHub REST API in March 2026. Query scope: open and closed issues mentioning tool execution, function calling, agent actions, side effects, or guard/check failures.

## Classification

2,332 issues classified as relevant to tool execution safety. Each issue was tagged with:

- **failure_pattern**: what went wrong (e.g. `tool_called_multiple`, `no_guard_before_call`, `cost_explosion`)
- **effect_type**: what real-world action was involved (e.g. `database_write`, `payment`, `email_send`)
- **signal_score**: 1-3 relevance score for agent-canary's detection scope

737 issues identified as directly validating agent-canary's core use case (missing guards, uncontrolled retries, cost explosions).

## Top patterns

| Pattern | Count | % of tags |
|---------|------:|----------:|
| tool_called_multiple | 1,075 | 25.0% |
| no_guard_before_call | 70 | 1.6% |
| cost_explosion | 128 | 3.0% |
| race_condition | 511 | 11.9% |
| interrupt_broken | 325 | 7.6% |

## Limitations

- Only public GitHub issues. Private repos and unreported incidents are not captured.
- Classification used keyword matching extended from a manually reviewed sample (~10-15% noise estimated).
- Data collected at a point in time (March 2026); issue counts will have changed since.
- Claude Code issues (1,450) represent 62% of the dataset, which skews aggregate counts toward that project's failure modes.
