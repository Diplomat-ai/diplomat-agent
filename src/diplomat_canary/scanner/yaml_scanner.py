"""YAML-based scanner — Mode 2.

Reads a diplomat-canary.yml config file and produces Tool objects
without AST analysis.
"""

from __future__ import annotations

from pathlib import Path

from diplomat_canary.models import Guard, SideEffect, Tool

_YAML_MISSING_MSG = (
    "PyYAML is not installed. Install it with:\n"
    "    pip install pyyaml\n"
    "\n"
    "Alternatively, use JSON mode: diplomat-canary --config config.json\n"
)


def _parse_side_effects(raw: list[dict], file_hint: str) -> list[SideEffect]:
    effects: list[SideEffect] = []
    for item in raw:
        category = item.get("category", "unknown")
        if category == "read":
            continue
        effects.append(
            SideEffect(
                category=category,
                evidence=item.get("evidence", f"declared in {file_hint}"),
                line=item.get("line", 0),
                file=item.get("file", file_hint),
            )
        )
    return effects


def _parse_guards(raw: list[dict]) -> list[Guard]:
    guards: list[Guard] = []
    for item in raw:
        guards.append(
            Guard(
                type=item.get("type", "unknown"),
                evidence=item.get("evidence", "declared in YAML"),
                line=item.get("line", 0),
                coverage=item.get("coverage", "full"),
            )
        )
    return guards


def _parse_params(raw: list[dict]) -> list[dict]:
    result: list[dict] = []
    for item in raw:
        result.append(
            {
                "name": item.get("name", "param"),
                "type": item.get("type", "unknown"),
                "has_bounds": item.get("has_bounds", False),
            }
        )
    return result


def load_yaml_config(config_path: Path) -> list[Tool]:
    """Parse a diplomat-canary.yml file and return Tool objects.

    Requires PyYAML to be installed.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        List of Tool objects as declared in the config.

    Raises:
        ImportError: If PyYAML is not installed.
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file is malformed.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(_YAML_MISSING_MSG) from exc

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid YAML config: expected a mapping, got {type(raw)}")

    tools_raw = raw.get("tools", [])
    if not isinstance(tools_raw, list):
        raise ValueError("Invalid YAML config: 'tools' must be a list")

    tools: list[Tool] = []
    for item in tools_raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "unknown_tool")
        file_hint = item.get("file", str(config_path))
        params = _parse_params(item.get("params", []))
        side_effects = _parse_side_effects(item.get("side_effects", []), file_hint)
        guards = _parse_guards(item.get("guards", []))

        # Skip tools with no write side effects (mirrors AST scanner behaviour)
        if not side_effects:
            continue

        tools.append(
            Tool(
                name=name,
                file=file_hint,
                line=item.get("line", 0),
                params=params,
                side_effects=side_effects,
                guards=guards,
                verdict="UNGUARDED",  # computed later by analyzer
            )
        )

    return tools


def generate_yaml_config(tools: list[Tool], output_path: Path) -> None:
    """Write a diplomat-canary.yml pre-populated from AST-detected tools.

    Falls back to a JSON-like YAML if PyYAML is not installed.

    Args:
        tools: List of Tool objects from the AST scanner.
        output_path: Where to write the YAML file.
    """
    try:
        import yaml  # type: ignore[import]

        _write_with_pyyaml(tools, output_path, yaml)
    except ImportError:
        _write_without_pyyaml(tools, output_path)


def _write_with_pyyaml(tools: list[Tool], output_path: Path, yaml) -> None:
    data: dict = {
        "agent": {"name": "my-agent"},
        "tools": [],
    }
    for tool in tools:
        entry: dict = {
            "name": tool.name,
            "file": tool.file,
            "line": tool.line,
            "params": [
                {"name": p["name"], "type": p["type"]} for p in tool.params
            ],
            "side_effects": [
                {"category": se.category} for se in tool.side_effects
            ],
            "guards": [
                {"type": g.type, "coverage": g.coverage} for g in tool.guards
            ],
        }
        data["tools"].append(entry)

    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _write_without_pyyaml(tools: list[Tool], output_path: Path) -> None:
    """Write a simplified YAML-compatible file without PyYAML."""
    lines: list[str] = [
        "agent:",
        "  name: my-agent",
        "",
        "tools:",
    ]
    for tool in tools:
        lines.append(f"  - name: {tool.name}")
        lines.append(f"    file: \"{tool.file}\"")
        lines.append(f"    line: {tool.line}")
        if tool.params:
            lines.append("    params:")
            for p in tool.params:
                lines.append(f"      - name: {p['name']}")
                lines.append(f"        type: {p['type']}")
        if tool.side_effects:
            lines.append("    side_effects:")
            for se in tool.side_effects:
                lines.append(f"      - category: {se.category}")
        if tool.guards:
            lines.append("    guards:")
            for g in tool.guards:
                lines.append(f"      - type: {g.type}")
                lines.append(f"        coverage: {g.coverage}")
        else:
            lines.append("    guards: []")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
