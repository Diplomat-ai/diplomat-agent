from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import diplomat_agent
from diplomat_agent.csaf.owasp_mapping import get_primary_category, get_owasp_reference, get_severity

def generate_advisory_id(seq: int, year: int | None = None) -> str:
    """Génère DIPLOMAT-YYYY-NNN."""
    if year is None:
        year = datetime.datetime.utcnow().year
    return f"DIPLOMAT-{year}-{seq:03d}"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _deduplicate_tools(tools: list[Any]) -> list[tuple[str, str, list[Any]]]:
    """Group tools by (name, primary_category). Returns (name, category, [tools])."""
    groups: dict[tuple[str, str], list[Any]] = {}
    for tool in tools:
        key = (tool.name, get_primary_category(tool))
        groups.setdefault(key, []).append(tool)
    return [(name, cat, members) for (name, cat), members in groups.items()]


def _group_to_vulnerability(
    name: str,
    category: str,
    members: list[Any],
    product_id: str,
) -> dict:
    """Convertit un groupe de Tools (même nom + catégorie) en bloc vulnerability CSAF."""
    sev_data = get_severity(category)
    ref = get_owasp_reference(category)

    # Build location list — one line per occurrence
    locations = []
    all_evidences = []
    for t in members:
        locations.append(f"{t.file}:{t.line}")
        for se in t.side_effects:
            if se.evidence not in all_evidences:
                all_evidences.append(se.evidence)

    location_str = ", ".join(locations)
    description = (
        f"Unguarded tool call '{name}' found at {len(members)} location(s): "
        f"{location_str}.\nEvidences:\n" + "\n".join(all_evidences)
    )

    vuln = {
        "title": f"Unguarded {category} via {name}",
        "cve": None,
        "notes": [
            {
                "category": "description",
                "text": description,
            },
            {
                "category": "general",
                "title": "Impact",
                "text": sev_data["impact_description"],
            },
        ],
        "product_status": {
            "known_affected": [product_id],
        },
        "scores": [
            {
                "products": [product_id],
                "cvss_v3": sev_data["cvss"],
            }
        ],
        "threats": [
            {
                "category": "exploit_status",
                "details": (
                    "This finding identifies an architectural vulnerability "
                    "(missing governance). Exploitability depends on the agent's "
                    "prompts and available context."
                ),
            }
        ],
        "remediations": [
            {
                "category": "mitigation",
                "details": (
                    "Add appropriate guards (input validation, human-in-the-loop "
                    "approval, rate limiting) or integrate Diplomat Control Plane "
                    "for runtime interception with <50ms verdicts and immutable "
                    "receipts."
                ),
                "product_ids": [product_id],
                "url": "https://diplomat.run/how-it-works",
            }
        ],
    }

    if ref:
        vuln["references"] = [
            {
                "category": "external",
                "summary": ref["summary"],
                "url": ref["url"],
            }
        ]

    return vuln


def _build_executive_summary(
    groups: list[tuple[str, str, list[Any]]],
    repo_name: str,
    total_unguarded: int,
) -> str:
    """Build an actionable executive summary with severity breakdown."""
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for _name, category, _members in groups:
        severity = get_severity(category)["cvss"].get("baseSeverity", "LOW")
        counts[severity] = counts.get(severity, 0) + 1

    parts = []
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if counts[sev]:
            parts.append(f"{counts[sev]} {sev}")
    breakdown = ", ".join(parts)

    summary = (
        f"diplomat-agent identified {total_unguarded} unguarded tool call(s) "
        f"in {repo_name}. After deduplication: {len(groups)} unique finding(s) "
        f"({breakdown})."
    )

    # Actionable priority sentence
    if counts["CRITICAL"]:
        summary += (
            f" Immediate action required: {counts['CRITICAL']} CRITICAL "
            f"finding(s) allow arbitrary code execution or destructive "
            f"operations without governance."
        )
    elif counts["HIGH"]:
        summary += (
            f" Priority action recommended: {counts['HIGH']} HIGH finding(s) "
            f"involve data destruction or uncontrolled agent invocation."
        )

    return summary

def scan_to_csaf(
    scan_result: Any,
    advisory_id: str,
    repo_name: str,
    repo_url: str = "",
    max_vulns: int = 50,
) -> dict:
    """
    Convertit un ScanResult diplomat-agent en document CSAF 2.0.
    """
    now = datetime.datetime.utcnow().isoformat() + "Z"
    document_title = f"AI Governance Advisory for {repo_name}"
    
    csaf = {
        "document": {
            "csaf_version": "2.0",
            "category": "csaf_vex",
            "title": document_title,
            "publisher": {
                "category": "coordinator",
                "name": "Diplomat Services",
                "namespace": "https://diplomat.run",
                "contact_details": "security@diplomat.run"
            },
            "tracking": {
                "id": advisory_id,
                "current_release_date": now,
                "initial_release_date": now,
                "revision_history": [
                    {
                        "number": "1",
                        "date": now,
                        "summary": "Initial advisory generation."
                    }
                ],
                "status": "final",
                "version": "1",
                "generator": {
                    "engine": {
                        "name": "diplomat-agent",
                        "version": diplomat_agent.__version__,
                    }
                },
            },
            "notes": [
                {
                    "category": "summary",
                    "title": "Executive Summary",
                    "text": "",  # placeholder — filled after dedup & severity analysis
                },
                {
                    "category": "legal_disclaimer",
                    "title": "Legal Disclaimer",
                    "text": "This advisory is generated by an automated static analysis tool. False positives and false negatives may occur.",
                },
            ],
            "aggregate_severity": {
                "text": "See individual findings.",
            }
        }
    }

    # Product Tree
    product_id = f"CSAFPID-{repo_name.replace('/', '-')}"
    csaf["product_tree"] = {
        "branches": [
            {
                "category": "architecture",
                "name": "Software",
                "branches": [
                    {
                        "category": "product_name",
                        "name": repo_name,
                        "product": {
                            "product_id": product_id,
                            "name": repo_name
                        }
                    }
                ]
            }
        ]
    }
    
    if repo_url:
        csaf["document"]["references"] = [
            {
                "category": "external",
                "summary": "Repository URL",
                "url": repo_url
            }
        ]
        
    # Filter unguarded tools, deduplicate, sort by severity
    unguarded = [t for t in scan_result.tools if t.verdict == "UNGUARDED" and not t.ignored]
    groups = _deduplicate_tools(unguarded)

    # Sort groups by CVSS severity (CRITICAL first, LOW last)
    groups.sort(
        key=lambda g: SEVERITY_ORDER.get(
            get_severity(g[1])["cvss"].get("baseSeverity", "LOW"),
            3,
        )
    )

    # Build executive summary (before truncation, so counts reflect the full picture)
    summary_text = _build_executive_summary(groups, repo_name, len(unguarded))
    csaf["document"]["notes"][0]["text"] = summary_text

    # Truncate to max_vulns and convert to CSAF vulnerabilities
    vulns = []
    for name, category, members in groups[:max_vulns]:
        vulns.append(_group_to_vulnerability(name, category, members, product_id))

    if vulns:
        csaf["vulnerabilities"] = vulns

    return csaf

def write_advisory(csaf: dict, output_path: str) -> None:
    """Écrit le document CSAF en JSON indenté."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(csaf, f, indent=2)
