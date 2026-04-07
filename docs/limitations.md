# Known limitations

> Back to [README](../README.md)

- **Static analysis only** — cannot detect runtime-generated tool calls or guards added at infrastructure level (API gateways, IAM, network policies)
- **Intra-procedural only** — `session.commit()` is flagged when no validation exists in the same function. If validation happens in a calling function, middleware, or ORM model validator, the scanner can't see it. Use `# checked:ok — validated in [where]` to acknowledge
- **HTTP writes don't distinguish internal vs external** — a POST to an internal health endpoint and a POST to a third-party API look identical in static analysis. Mark internal calls with `# checked:ok — internal service`
- **`name_contains` patterns** (e.g. "refund", "charge") may match internal business methods that aren't actual payment operations (~22% FP rate on payment patterns)
- **No import alias resolution** — `import requests as r` then `r.post()` is not detected
- **Python only** — TypeScript on the roadmap
