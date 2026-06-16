# Known limitations

> Back to [README](../README.md)

- **Static analysis only** — cannot detect runtime-generated tool calls or guards added at infrastructure level (API gateways, IAM, network policies)
- **Intra-procedural only** — `session.commit()` is flagged when no validation exists in the same function. If validation happens in a calling function, middleware, or ORM model validator, the scanner can't see it. Use `# checked:ok — validated in [where]` to acknowledge
- **HTTP writes don't distinguish internal vs external** — a POST to an internal health endpoint and a POST to a third-party API look identical in static analysis. Mark internal calls with `# checked:ok — internal service`
- **`name_contains` patterns** (e.g. "refund", "charge") may match internal business methods that aren't actual payment operations (~22% FP rate on payment patterns)
- **No import alias resolution** — `import requests as r` then `r.post()` is not detected
- **Python only** — TypeScript on the roadmap

## OPAQUE verdict — by design

`OPAQUE` is not a risk rating. It means the effect surface could not be statically resolved and requires manual review.

This verdict is intentional in three situations:

- **External library callables** — when an MCP tool passes a callable into a third-party executor (e.g. `asyncio.to_thread(fn)`, `executor.submit(fn)`), the callable's body is outside the scan unit. diplomat-agent surfaces it as OPAQUE rather than silently under-reporting.
- **Dispatcher indirection** — `@server.call_tool` handlers receive a tool name at runtime. The scanner resolves branches it can see; branches pointing outside the package produce OPAQUE.
- **MCP client proxies** — `session.call_tool(...)` routes to a remote server. The real effect is server-side and invisible to static analysis.

`readOnlyHint: true` in an MCP tool description is **not trusted** by diplomat-agent. A dispatcher handler that declares itself read-only but calls an external executable or passes a callable to an executor is still reported as OPAQUE until the implementation can be verified.
