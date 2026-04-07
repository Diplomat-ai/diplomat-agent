# Acknowledging tool calls

> Back to [README](../README.md)

If a tool call is intentionally unguarded or protected elsewhere:

```python
def send_alert(message):  # checked:ok — protected by API gateway
    requests.post(ALERT_URL, json={"msg": message})
```

`# diplomat:ok`, `# checked:ok`, and `# canary:ok` all work.

Every `# checked:ok` annotation appears in `toolcalls.yaml` with its justification. Reviewers can audit acknowledgments in PRs — no tool call disappears silently.
