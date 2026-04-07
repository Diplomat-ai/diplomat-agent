"""OWASP mapping for diplomat-agent side effects."""

from __future__ import annotations

from typing import Any

# Identifiants EXACTS tels qu'ils apparaissent dans SideEffect.category
CATEGORY_SEVERITY_ORDER = [
    "destructive",
    "payment",
    "database_delete",
    "file_delete",
    "agent_invocation",
    "database_write",
    "http_write",
    "email",
    "llm_call",
    "publish",
]

CATEGORY_MAP = {
    "destructive": {
        "owasp_id": "LLM05",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H",
            "baseScore": 9.9,
            "baseSeverity": "CRITICAL",
        },
        "impact_description": (
            "Unguarded subprocess/exec/eval allows AI agent to execute arbitrary "
            "system commands. Maps to OWASP LLM05 Improper Output Handling."
        ),
    },
    "payment": {
        # Sévérité intentionnellement MEDIUM et non CRITICAL
        # Raison : ~22% de faux positifs sur les patterns payment
        # (match sur des méthodes internes comme quota_charge.refund())
        # Voir REALITY_CHECK_RESULTS.md pour le détail
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N",
            "baseScore": 6.5,
            "baseSeverity": "MEDIUM",
        },
        "impact_description": (
            "Potential unguarded payment operation. CAUTION: ~22% false positive "
            "rate on payment patterns. Verify before acting."
        ),
    },
    "database_delete": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:H",
            "baseScore": 8.1,
            "baseSeverity": "HIGH",
        },
        "impact_description": (
            "Unguarded database delete allows AI agent to irrecoverably destroy "
            "data without human approval. Maps to OWASP LLM06 Excessive Agency."
        ),
    },
    "file_delete": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:H",
            "baseScore": 8.1,
            "baseSeverity": "HIGH",
        },
        "impact_description": (
            "Unguarded file deletion allows AI agent to destroy local data "
            "without confirmation. Maps to OWASP LLM06 Excessive Agency."
        ),
    },
    "agent_invocation": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:H/A:L",
            "baseScore": 8.5,
            "baseSeverity": "HIGH",
        },
        "impact_description": (
            "Unguarded agent invocation allows recursive or chained agent "
            "execution without bounds. Maps to OWASP LLM06 Excessive Agency."
        ),
    },
    "database_write": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N",
            "baseScore": 6.5,
            "baseSeverity": "MEDIUM",
        },
        "impact_description": (
            "Unguarded database write allows AI agent to modify persistent data "
            "without human validation. Maps to OWASP LLM06 Excessive Agency."
        ),
    },
    "http_write": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:L/A:N",
            "baseScore": 5.0,
            "baseSeverity": "MEDIUM",
        },
        "impact_description": (
            "Unguarded HTTP write (POST/PUT/PATCH) allows AI agent to modify "
            "external system state without validation. Maps to OWASP LLM06."
        ),
    },
    "email": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:L/A:N",
            "baseScore": 5.0,
            "baseSeverity": "MEDIUM",
        },
        "impact_description": (
            "Unguarded email send allows AI agent to communicate externally "
            "without human oversight. Maps to OWASP LLM06 Excessive Agency."
        ),
    },
    "llm_call": {
        "owasp_id": "LLM01",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N",
            "baseScore": 4.8,
            "baseSeverity": "MEDIUM",
        },
        "impact_description": (
            "Unguarded LLM call without input/output controls creates a vector "
            "for indirect prompt injection. Maps to OWASP LLM01 Prompt Injection."
        ),
    },
    "publish": {
        "owasp_id": "LLM06",
        "cvss": {
            "version": "3.1",
            "vectorString": "CVSS:3.1/AV:N/AC:H/PR:L/UI:N/S:U/C:N/I:L/A:N",
            "baseScore": 3.1,
            "baseSeverity": "LOW",
        },
        "impact_description": (
            "Unguarded publish/upload operation. NOTE: High false positive rate. "
            "Manual review recommended."
        ),
    },
}

def get_primary_category(tool: Any) -> str:
    """
    Un Tool peut avoir plusieurs side_effects de catégories différentes.
    Retourne la catégorie de sévérité la plus haute selon CATEGORY_SEVERITY_ORDER.
    Si aucun side_effect, retourne "unknown".
    """
    if not tool.side_effects:
        return "unknown"
        
    categories = {se.category for se in tool.side_effects}
    for cat in CATEGORY_SEVERITY_ORDER:
        if cat in categories:
            return cat
            
    # S'il y a des catégories inconnues
    return list(categories)[0]

CATEGORY_MAP["subprocess_exec"] = CATEGORY_MAP["destructive"]

OWASP_LLM_2025 = {
    "LLM01": {
        "name": "Prompt Injection",
        "url": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
    },
    "LLM02": {
        "name": "Sensitive Information Disclosure",
        "url": "https://genai.owasp.org/llmrisk/llm02-sensitive-information-disclosure/",
    },
    "LLM03": {
        "name": "Supply Chain",
        "url": "https://genai.owasp.org/llmrisk/llm03-supply-chain/",
    },
    "LLM04": {
        "name": "Data and Model Poisoning",
        "url": "https://genai.owasp.org/llmrisk/llm04-data-and-model-poisoning/",
    },
    "LLM05": {
        "name": "Improper Output Handling",
        "url": "https://genai.owasp.org/llmrisk/llm05-improper-output-handling/",
    },
    "LLM06": {
        "name": "Excessive Agency",
        "url": "https://genai.owasp.org/llmrisk/llm06-excessive-agency/",
    },
    "LLM07": {
        "name": "System Prompt Leakage",
        "url": "https://genai.owasp.org/llmrisk/llm07-system-prompt-leakage/",
    },
    "LLM08": {
        "name": "Vector and Embedding Weaknesses",
        "url": "https://genai.owasp.org/llmrisk/llm08-vector-and-embedding-weaknesses/",
    },
    "LLM09": {
        "name": "Misinformation",
        "url": "https://genai.owasp.org/llmrisk/llm09-misinformation/",
    },
    "LLM10": {
        "name": "Unbounded Consumption",
        "url": "https://genai.owasp.org/llmrisk/llm10-unbounded-consumption/",
    },
}

def get_owasp_reference(category: str) -> dict | None:
    """Retourne {"summary": "OWASP LLMxx:2025 Name", "url": "..."} ou None."""
    data = CATEGORY_MAP.get(category)
    if not data:
        return None
    owasp_id = data["owasp_id"]
    owasp_info = OWASP_LLM_2025.get(owasp_id)
    if not owasp_info:
        return None
        
    return {
        "summary": f"OWASP {owasp_id}:2025 {owasp_info['name']}",
        "url": owasp_info["url"]
    }

def get_severity(category: str) -> dict:
    """Retourne {"cvss": {...}, "impact_description": "..."}. Fallback sur http_write."""
    data = CATEGORY_MAP.get(category)
    if not data:
        data = CATEGORY_MAP["http_write"]
    return {
        "cvss": data["cvss"],
        "impact_description": data["impact_description"]
    }
