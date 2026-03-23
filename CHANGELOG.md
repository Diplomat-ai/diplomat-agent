# Changelog

All notable changes to agent-canary will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- `toolcalls.yaml` registry output (`--format registry`)
- `--fail-on-unchecked` CI gate with baseline support
- `# checked:ok` annotation (+ `# canary:ok` backward compatible)
- Terminal footer with 4 resolution options
- Effect-type priority ordering in NO CHECKS section

### Changed
- Summary line: "X tool calls · Y no checks · Z partial · W confirmed"

## [0.1.0] - 2026-03-XX

### Added
- AST-based Python scanner for tool calls with real-world effects
- Detection: database writes/deletes, HTTP writes, payments, email, messaging, LLM calls, dynamic code
- Check detection: input validation, rate limits, auth (Depends/Security), confirmation, idempotency, retry bounds
- Output formats: terminal, markdown, JSON
- `--fail-on-unguarded` CI mode
- `# canary:ok` inline annotation
- YAML config mode for dynamic tools
- Benchmarked on Skyvern, FinRobot, SurfSense
