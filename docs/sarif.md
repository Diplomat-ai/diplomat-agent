# SARIF output for GitHub Code Scanning

diplomat-agent can produce [SARIF v2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) output, the format consumed by GitHub Code Scanning.

## Usage

```bash
# Write to file
diplomat-agent . --format sarif -o results.sarif

# Pipe to stdout
diplomat-agent . --format sarif
```

## GitHub Actions integration

```yaml
name: Diplomat governance scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4

      - name: Run diplomat-agent
        run: |
          pip install diplomat-agent
          diplomat-agent . --format sarif -o results.sarif

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

This makes diplomat-agent findings appear in the **Security** tab of your GitHub repository, alongside CodeQL and other SAST results.

## SARIF structure

Each tool function with side effects becomes a SARIF `result`:

| SARIF field | Source |
|-------------|--------|
| `ruleId` | `diplomat-agent/{verdict}-{category}` (e.g. `diplomat-agent/unguarded-payment`) |
| `level` | `warning` (UNGUARDED), `note` (PARTIALLY_GUARDED), `none` (GUARDED) |
| `message.text` | Function name and missing checks |
| `locations[0]` | File path and line number |
| `properties.owasp` | OWASP Agentic Top 10 codes |
| `properties.checks` | Existing guards detected |
| `properties.missing` | Missing governance checks |

Rule definitions include `helpUri` pointing to the [OWASP Agentic mapping](owasp-agentic-mapping.md) and OWASP codes as tags.

## No dependencies

SARIF output uses only the stdlib `json` module. No additional packages required.
