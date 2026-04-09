# Behavioral BOM: what your agent can do

## The problem

AI-BOMs (CycloneDX, SPDX AI Profile) inventory what an agent is *made of* — models, libraries, datasets, training data, fine-tuning parameters. They answer: "what components are in this system?"

They don't answer: "what can this system *do* to the real world?"

An AI agent that calls `stripe.Refund.create()`, `session.delete()`, and `subprocess.run()` has capabilities that don't appear in any component inventory. These capabilities are encoded in the source code, in the tool functions that the agent can invoke.

## The gap

OWASP recommends: "maintain a complete inventory of all agentic components, including... tools available to agents, along with their permissions and access levels" ([OWASP Agentic Security](https://genai.owasp.org)).

NIST launched the AI Agent Standards Initiative (February 2026) with a focus on interoperability — which implies agents need to declare their capabilities.

Neither defines a format for per-tool-call behavioral inventory at the source code level.

## toolcalls.yaml as behavioral BOM

diplomat-agent generates `toolcalls.yaml` — a file that answers three questions for every tool call in your codebase:

1. **What action does it perform?** (e.g. `stripe.Refund.create(amount=amount)`)
2. **What checks exist?** (e.g. `auth_check: Depends(get_current_user)`)
3. **What checks are missing?** (e.g. `no bounds on amount`, `no rate limit`)

The file is:
- **Diffable** — changes show up in `git diff` and PR reviews
- **Committable** — lives in the repo alongside the code it describes
- **Regenerable** — produced from scratch on each scan, no manual maintenance
- **Machine-readable** — YAML format, parseable by CI pipelines and policy engines

## Relationship to existing standards

| Standard | What it inventories | Relationship to toolcalls.yaml |
|----------|--------------------|-----------------------------|
| CycloneDX | Components (libraries, models, datasets) | Complementary — what's in the box |
| SPDX AI Profile | Same + training data, hyperparameters | Complementary — what's in the box |
| toolcalls.yaml | Tool call capabilities + governance state | What the box can *do* |

These are different layers of the same system. A complete audit needs both: what the agent is made of (CycloneDX) and what it can do (toolcalls.yaml).

## Specification

See [toolcalls.yaml specification](toolcalls-yaml-spec.md) for the format definition.

## Generate it

```bash
diplomat-agent . --format registry --output-registry toolcalls.yaml
```
