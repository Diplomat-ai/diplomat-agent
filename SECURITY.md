# Security Policy

## Reporting a vulnerability

Do not open a public GitHub issue for security vulnerabilities.

**Email**: josselin@diplomat.run
**Response time**: 48 hours

## Scope

agent-canary runs entirely locally. It makes no network calls and collects no telemetry. It only reads Python files — it does not execute them.

Vulnerabilities in scope:
- Malicious Python files that cause unexpected behavior during AST parsing
- Patterns that create false negatives on critical tool calls (e.g. payment functions not detected)
- Bypass of `--fail-on-unchecked` CI gate

## Out of scope

- Vulnerabilities in scanned codebases (agent-canary reports them, it doesn't fix them)
- Feature requests (use GitHub issues)
