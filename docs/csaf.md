# CSAF 2.0 Advisory

> Back to [README](../README.md)

Generate a security advisory in CSAF 2.0 format (the OASIS standard used by CERTs and security teams):

```bash
diplomat-agent . --format csaf --output advisory.csaf.json
```

The generated advisory includes:

- An **executive summary** with severity breakdown, e.g.: *"diplomat-agent identified 127 unguarded tool call(s) in khoj. After deduplication: 120 unique finding(s) (4 CRITICAL, 33 HIGH, 81 MEDIUM, 2 LOW). Immediate action required: 4 CRITICAL finding(s) allow arbitrary code execution or destructive operations without governance."*
- **Vulnerabilities sorted by CVSS severity** (CRITICAL first, LOW last)
- **OWASP LLM Top 10 2025 mapping** for each finding
- **Remediation guidance** and product tree
- **Automatic deduplication** -- same function + same category = one vulnerability entry

Control the maximum number of vulnerabilities in the output with `--max-vulns N` (default: 50).

Use case: hand the `.csaf.json` file to your security team, RSSI, or auditor -- no extra configuration needed.

<details>
<summary><strong>OWASP LLM Top 10 mapping</strong></summary>

Each CSAF vulnerability is automatically mapped to the OWASP LLM Top 10 (2025):

| Side-effect category | OWASP LLM | Severity |
|---|---|---|
| destructive (subprocess, exec, eval) | LLM05 Improper Output Handling | CRITICAL |
| database_delete, file_delete | LLM06 Excessive Agency | HIGH |
| agent_invocation | LLM06 Excessive Agency | HIGH |
| database_write, http_write, email, publish, payment | LLM06 Excessive Agency | MEDIUM |
| llm_call | LLM01 Prompt Injection | MEDIUM |

</details>

## CI integration: CSAF artifact

Generate and archive a CSAF advisory as CI artifact:

```yaml
- name: Diplomat CSAF advisory
  run: |
    pip install diplomat-agent
    diplomat-agent . --format csaf --output diplomat-advisory.csaf.json
- uses: actions/upload-artifact@v4
  with:
    name: csaf-advisory
    path: diplomat-advisory.csaf.json
```
