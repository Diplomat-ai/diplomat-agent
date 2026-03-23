#!/usr/bin/env python3
"""
diplomat-canary — GitHub issue collector v2
Collecte et classifie les issues de 4 repos de frameworks agentiques.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DATA_DIR = Path(__file__).parent

REPOS = [
    ("langchain-ai", "langgraph"),
    ("crewAIInc", "crewAI"),
    ("microsoft", "autogen"),
]

KEYWORDS_A = [
    "tool call", "tool_call", "tool use", "tool_use", "tool execution",
    "toolnode", "tool result", "tool_result", "tool_call_id",
    "@tool", "basetool", "execute_tool", "run_tool",
    "write", "insert", "update", "delete", "send", "emit", "publish",
    "database", " db ", "postgres", "redis", "mongo",
    "email", "smtp", "webhook", "payment", "stripe", "api call",
    "external api", "side effect", "irreversible",
]

KEYWORDS_B = [
    "production", " prod ", "deployed", "deployment",
    "unexpected", "unintended", "wrong", "incorrect", "duplicate",
    "loop", "infinite loop", "retry", "repeated", "multiple times",
    "race condition", "concurrent", "parallel tool",
    "interrupt", "human-in-the-loop", "hitl", "approval",
    "budget", "cost", "token limit", "rate limit",
    "injection", "exfiltration", "malicious", "skill",
]

# ── API helpers ──────────────────────────────────────────────────────────────
def api_get(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"token {TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "diplomat-canary-collector/2.0",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                if attempt == 0 and int(remaining or 999) < 20:
                    print(f"  [warn] rate limit low: {remaining} remaining", file=sys.stderr)
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 403 and attempt < retries - 1:
                print(f"  [rate limit] waiting 60s...", file=sys.stderr)
                time.sleep(60)
                continue
            raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            raise
    return []

MIN_DATE = "2026-01-01"

def list_issues_raw(owner: str, repo: str, state: str, page: int) -> list:
    """Returns raw list from API (includes PRs), used for pagination logic."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues"
        f"?state={state}&per_page=100&page={page}&sort=updated&direction=desc"
    )
    result = api_get(url)
    return result if result else []

def list_issues(owner: str, repo: str, state: str, page: int) -> list:
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues"
        f"?state={state}&per_page=100&page={page}&sort=updated&direction=desc"
    )
    result = api_get(url)
    if result is None:
        return []
    # Filter out pull requests
    return [i for i in result if "pull_request" not in i]

def is_after_cutoff(issue: dict) -> bool:
    updated = issue.get("updated_at") or issue.get("created_at") or ""
    return updated >= MIN_DATE

def get_comments(owner: str, repo: str, issue_number: int) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=50"
    result = api_get(url)
    return result if result else []

# ── Classification ───────────────────────────────────────────────────────────
def is_relevant(issue: dict) -> bool:
    text = ((issue.get("title") or "") + " " + (issue.get("body") or "")).lower()
    for kw in KEYWORDS_A + KEYWORDS_B:
        if kw in text:
            return True
    return False

def classify(issue: dict, repo_full: str) -> dict:
    text = ((issue.get("title") or "") + " " + (issue.get("body") or "")).lower()

    # production_signal
    prod_markers = ["production", " prod ", "deployed", "our system", "our agent",
                    "we have code running", "real users", "in production",
                    "emails sent", "database modified", "payment triggered"]
    production_signal = any(m in text for m in prod_markers)

    # effect_type
    effect_type = []
    if any(k in text for k in ["insert", "update", "delete", "upsert", "database", "postgres", "redis", "mongo", "db write", "database_write"]):
        effect_type.append("database_write")
    if any(k in text for k in ["stripe", "twilio", "slack api", "external api", "api call", "third-party", "webhook"]):
        effect_type.append("api_call_external")
    if any(k in text for k in ["email", "smtp", "sendgrid", "mailgun", "ses "]):
        effect_type.append("email_send")
    if any(k in text for k in ["file write", "file_write", "open(", "os.write", "write to file"]):
        effect_type.append("file_write")
    if any(k in text for k in ["payment", "stripe", "charge", "transaction", "billing"]):
        effect_type.append("payment")
    if any(k in text for k in ["telegram", "whatsapp", "discord", "message send", "message_send", "sms"]):
        effect_type.append("message_send")
    if any(k in text for k in ["delete", "drop table", "data_delete", "purge"]):
        if "data_delete" not in effect_type:
            effect_type.append("data_delete")
    if any(k in text for k in ["write", "send", "emit", "publish", "insert", "update", "tool execution"]):
        if not effect_type:
            effect_type.append("unknown_write")
    if not effect_type:
        effect_type.append("read_only")

    # failure_pattern
    failure_pattern = []
    if any(k in text for k in ["not called", "not executed", "not invoked", "simulated", "hallucinated"]):
        failure_pattern.append("tool_not_called")
    if any(k in text for k in ["multiple times", "loop", "repeated", "duplicate", "twice", "called again", "called multiple", "infinite"]):
        failure_pattern.append("tool_called_multiple")
    if any(k in text for k in ["wrong param", "wrong args", "incorrect param", "wrong argument", "invalid param"]):
        failure_pattern.append("tool_wrong_params")
    if any(k in text for k in ["tool_result", "orphan", "tool_call_id", "mismatch"]):
        failure_pattern.append("tool_result_orphan")
    if any(k in text for k in ["interrupt", "human-in-the-loop", "hitl", "approval", "breakpoint"]):
        if any(k in text for k in ["broken", "not working", "fails", "doesn't work", "bug", "wrong", "incorrect"]):
            failure_pattern.append("interrupt_broken")
        else:
            failure_pattern.append("interrupt_broken")
    if any(k in text for k in ["resume value", "interrupt misrouted", "wrong tool", "misrouted"]):
        failure_pattern.append("interrupt_misrouted")
    if any(k in text for k in ["breaking change", "upgrade", "version", "migration", "deprecated", "broke after"]):
        failure_pattern.append("breaking_change")
    if any(k in text for k in ["no validation", "without check", "unguarded", "no guard", "missing check", "no confirmation"]):
        failure_pattern.append("no_guard_before_call")
    if any(k in text for k in ["cost explosion", "token explosion", "retry loop", "rate limit", "budget", "too many tokens"]):
        failure_pattern.append("cost_explosion")
    if any(k in text for k in ["race condition", "concurrent", "parallel", "async", "thread"]):
        failure_pattern.append("race_condition")
    if any(k in text for k in ["skill", "mcp", "supply chain", "third-party tool", "external tool"]):
        failure_pattern.append("supply_chain")
    if not failure_pattern:
        failure_pattern = []

    # relevance_for_canary
    core_signals = ["tool execution", "tool call", "tool_call", "side effect", "irreversible",
                    "no guard", "unguarded", "no validation", "before call", "interrupt",
                    "tool_called_multiple", "tool_not_called", "no_guard_before_call",
                    "race condition", "duplicate tool", "tool called twice"]
    adjacent_signals = ["deployment", "auth", "authentication", "authorization", "token limit", "rate limit"]

    if any(k in text for k in core_signals) or "no_guard_before_call" in failure_pattern or "interrupt_broken" in failure_pattern:
        relevance_for_canary = "core"
    elif any(k in text for k in adjacent_signals) or "breaking_change" in failure_pattern:
        relevance_for_canary = "adjacent"
    elif production_signal:
        relevance_for_canary = "signal"
    else:
        relevance_for_canary = "noise"

    # signal_score
    score = 0
    if is_relevant(issue):
        score = 1
    if "failure_pattern" and failure_pattern:
        score = max(score, 2)
    if production_signal and failure_pattern and any(e != "read_only" for e in effect_type):
        score = max(score, 2)
    if production_signal and ("unknown_write" in effect_type or "database_write" in effect_type or
                               "email_send" in effect_type or "payment" in effect_type or
                               "api_call_external" in effect_type):
        score = max(score, 3)
    if relevance_for_canary == "core" and failure_pattern and production_signal:
        score = 3
    if score == 3 and not failure_pattern:
        score = 2

    # fix_status
    state = issue.get("state", "open")
    if state == "open":
        fix_status = "open"
    else:
        labels = [l.get("name", "").lower() for l in (issue.get("labels") or [])]
        if any(l in labels for l in ["wontfix", "won't fix", "not a bug", "invalid"]):
            fix_status = "closed_wontfix"
        elif any(l in labels for l in ["stale", "duplicate"]):
            fix_status = "closed_wontfix"
        else:
            fix_status = "unknown"

    return {
        "signal_score": score,
        "production_signal": production_signal,
        "effect_type": effect_type,
        "failure_pattern": failure_pattern,
        "relevance_for_canary": relevance_for_canary,
        "fix_status": fix_status,
    }

def make_summary(issue: dict, classification: dict) -> str:
    title = issue.get("title", "")
    body = (issue.get("body") or "")[:300]
    patterns = ", ".join(classification.get("failure_pattern", [])) or "unknown"
    return f"{title[:80]}. Pattern(s): {patterns}."

def make_canary_note(issue: dict, classification: dict) -> str:
    patterns = classification.get("failure_pattern", [])
    effects = classification.get("effect_type", [])
    rel = classification.get("relevance_for_canary", "noise")
    if rel == "core":
        return (
            f"diplomat-canary devrait détecter: {', '.join(effects)} "
            f"avec patterns [{', '.join(patterns)}]. "
            f"Issue illustre un tool call sans protection avant exécution."
        )
    elif rel == "adjacent":
        return f"Hors scope direct mais lié: {', '.join(patterns)}."
    else:
        return f"Signal faible: {', '.join(effects)}."

# ── Main collection ──────────────────────────────────────────────────────────
def main():
    session_start = datetime.now(timezone.utc).isoformat()
    print(f"[{session_start}] Starting collection...", file=sys.stderr)

    raw_path = DATA_DIR / "issues_raw.jsonl"
    classified_path = DATA_DIR / "issues_classified.jsonl"

    # Load existing issue numbers to avoid duplicates
    existing_raw = set()
    if raw_path.exists():
        with open(raw_path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing_raw.add((d["repo"], d["issue_number"]))
                except Exception:
                    pass

    existing_classified = set()
    if classified_path.exists():
        with open(classified_path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    existing_classified.add((d["repo"], d["issue_number"]))
                except Exception:
                    pass

    print(f"Existing raw: {len(existing_raw)}, classified: {len(existing_classified)}", file=sys.stderr)

    log = {
        "session_date": session_start,
        "repos_queried": [],
        "api_calls_made": 0,
        "issues_per_repo": {},
        "errors": [],
        "mcp_version": "curl-rest-api-v2",
        "next_run_cursor": {},
        "blind_spots": [],
    }

    all_classified = []
    total_new_raw = 0
    total_new_classified = 0

    with open(raw_path, "a") as f_raw, open(classified_path, "a") as f_cls:
        for owner, repo in REPOS:
            repo_full = f"{owner}/{repo}"
            print(f"\n=== Collecting {repo_full} ===", file=sys.stderr)
            log["repos_queried"].append(repo_full)
            log["issues_per_repo"][repo_full] = {"open": 0, "closed": 0, "comments_fetched": 0, "new": 0}

            repo_new_raw = 0
            repo_new_classified = 0
            issues_this_repo = []

            # Open issues: up to 10 pages (stop only on truly empty raw response)
            for page in range(1, 11):
                print(f"  Fetching open issues page {page}...", file=sys.stderr)
                raw_issues = list_issues_raw(owner, repo, "open", page)
                log["api_calls_made"] += 1
                filtered = [i for i in raw_issues if "pull_request" not in i]
                print(f"  Got {len(filtered)} open issues (page {page}, raw={len(raw_issues)})", file=sys.stderr)
                if not raw_issues:
                    break
                all_before_cutoff = all(not is_after_cutoff(i) for i in raw_issues)
                for issue in filtered:
                    if not is_after_cutoff(issue):
                        continue
                    key = (repo_full, issue["number"])
                    if key not in existing_raw:
                        existing_raw.add(key)
                        issues_this_repo.append((issue, "open"))
                        log["issues_per_repo"][repo_full]["open"] += 1
                        repo_new_raw += 1
                time.sleep(0.5)
                if len(raw_issues) < 100 or all_before_cutoff:
                    break  # Last page or all issues before cutoff date

            # Closed issues: up to 8 pages
            for page in range(1, 9):
                print(f"  Fetching closed issues page {page}...", file=sys.stderr)
                raw_issues = list_issues_raw(owner, repo, "closed", page)
                log["api_calls_made"] += 1
                filtered = [i for i in raw_issues if "pull_request" not in i]
                print(f"  Got {len(filtered)} closed issues (page {page}, raw={len(raw_issues)})", file=sys.stderr)
                if not raw_issues:
                    break
                all_before_cutoff = all(not is_after_cutoff(i) for i in raw_issues)
                for issue in filtered:
                    if not is_after_cutoff(issue):
                        continue
                    key = (repo_full, issue["number"])
                    if key not in existing_raw:
                        existing_raw.add(key)
                        issues_this_repo.append((issue, "closed"))
                        log["issues_per_repo"][repo_full]["closed"] += 1
                        repo_new_raw += 1
                time.sleep(0.5)
                if len(raw_issues) < 100 or all_before_cutoff:
                    break  # Last page or all issues before cutoff date

            # Process issues
            for issue, state in issues_this_repo:
                relevant = is_relevant(issue)
                raw_entry = {
                    "repo": repo_full,
                    "issue_number": issue["number"],
                    "title": issue.get("title", ""),
                    "state": state,
                    "created_at": issue.get("created_at"),
                    "updated_at": issue.get("updated_at"),
                    "closed_at": issue.get("closed_at"),
                    "labels": [l["name"] for l in (issue.get("labels") or [])],
                    "assignees": [a["login"] for a in (issue.get("assignees") or [])],
                    "comments_count": issue.get("comments", 0),
                    "url": issue.get("html_url", ""),
                    "author_login": (issue.get("user") or {}).get("login", ""),
                    "author_type": (issue.get("user") or {}).get("type", "User"),
                    "body": (issue.get("body") or "")[:2000],
                    "relevant": relevant,
                }
                f_raw.write(json.dumps(raw_entry, ensure_ascii=False) + "\n")
                total_new_raw += 1

                if relevant:
                    cls_key = (repo_full, issue["number"])
                    if cls_key not in existing_classified:
                        existing_classified.add(cls_key)
                        classification = classify(issue, repo_full)
                        comments_fetched = False
                        comments_summary = None

                        if classification["signal_score"] >= 2:
                            try:
                                comments = get_comments(owner, repo, issue["number"])
                                log["api_calls_made"] += 1
                                log["issues_per_repo"][repo_full]["comments_fetched"] += 1
                                if comments:
                                    comments_text = " | ".join(
                                        (c.get("body") or "")[:200] for c in comments[:5]
                                    )
                                    comments_summary = comments_text[:500]
                                    # Re-classify with comments
                                    combined = issue.copy()
                                    combined["body"] = (issue.get("body") or "") + " " + comments_text
                                    classification = classify(combined, repo_full)
                                comments_fetched = True
                                time.sleep(0.3)
                            except Exception as e:
                                log["errors"].append({"type": "comment_fetch_error", "issue": issue["number"], "error": str(e)})

                        classified_entry = {
                            "repo": repo_full,
                            "issue_number": issue["number"],
                            "title": issue.get("title", ""),
                            "url": issue.get("html_url", ""),
                            "state": state,
                            "created_at": issue.get("created_at"),
                            "updated_at": issue.get("updated_at"),
                            **classification,
                            "summary": make_summary(issue, classification),
                            "canary_note": make_canary_note(issue, classification),
                            "comments_fetched": comments_fetched,
                            "comments_summary": comments_summary,
                        }
                        f_cls.write(json.dumps(classified_entry, ensure_ascii=False) + "\n")
                        all_classified.append(classified_entry)
                        total_new_classified += 1
                        repo_new_classified += 1

            log["issues_per_repo"][repo_full]["new"] = repo_new_raw
            print(f"  New raw: {repo_new_raw}, new classified: {repo_new_classified}", file=sys.stderr)

    # Load ALL classified for summary
    all_classified_all = []
    with open(classified_path) as f:
        for line in f:
            try:
                all_classified_all.append(json.loads(line))
            except Exception:
                pass

    # ── Generate patterns_summary.json ──────────────────────────────────────
    by_repo = {}
    for entry in all_classified_all:
        r = entry["repo"]
        if r not in by_repo:
            by_repo[r] = {
                "collected": 0,
                "relevant": 0,
                "signal_score_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
                "top_failure_patterns": {},
                "open_core_issues": [],
            }
        by_repo[r]["relevant"] += 1
        score = str(entry.get("signal_score", 0))
        by_repo[r]["signal_score_distribution"][score] = by_repo[r]["signal_score_distribution"].get(score, 0) + 1
        for p in entry.get("failure_pattern", []):
            by_repo[r]["top_failure_patterns"][p] = by_repo[r]["top_failure_patterns"].get(p, 0) + 1
        if entry.get("state") == "open" and entry.get("relevance_for_canary") == "core":
            by_repo[r]["open_core_issues"].append({
                "issue_number": entry["issue_number"],
                "title": entry["title"],
                "url": entry["url"],
                "signal_score": entry["signal_score"],
            })

    # Count raw per repo
    raw_counts = {}
    with open(raw_path) as f:
        for line in f:
            try:
                d = json.loads(line)
                raw_counts[d["repo"]] = raw_counts.get(d["repo"], 0) + 1
            except Exception:
                pass
    for r in by_repo:
        by_repo[r]["collected"] = raw_counts.get(r, 0)
        by_repo[r]["top_failure_patterns"] = sorted(
            by_repo[r]["top_failure_patterns"].items(), key=lambda x: -x[1]
        )[:5]
        by_repo[r]["open_core_issues"] = sorted(
            by_repo[r]["open_core_issues"], key=lambda x: -x["signal_score"]
        )[:10]

    # Cross-repo patterns
    pattern_names = [
        "tool_called_multiple", "interrupt_broken", "tool_not_called",
        "no_guard_before_call", "tool_result_orphan", "breaking_change",
        "race_condition", "supply_chain", "cost_explosion", "interrupt_misrouted",
    ]
    cross_repo_patterns = {}
    for pname in pattern_names:
        repos_with = set()
        count = 0
        open_count = 0
        closed_fixed = 0
        for entry in all_classified_all:
            if pname in entry.get("failure_pattern", []):
                count += 1
                repos_with.add(entry["repo"])
                if entry.get("fix_status") == "open":
                    open_count += 1
                elif entry.get("fix_status") == "closed_fixed":
                    closed_fixed += 1
        cross_repo_patterns[pname] = {
            "count": count,
            "repos": list(repos_with),
            "open": open_count,
            "closed_fixed": closed_fixed,
        }

    # Top signal issues
    top_signal = sorted(all_classified_all, key=lambda x: -x.get("signal_score", 0))[:10]
    top_signal_out = [{
        "repo": e["repo"],
        "issue_number": e["issue_number"],
        "title": e["title"],
        "url": e["url"],
        "signal_score": e["signal_score"],
        "relevance_for_canary": e["relevance_for_canary"],
    } for e in top_signal]

    core_count = sum(1 for e in all_classified_all if e.get("relevance_for_canary") == "core")
    top_patterns = sorted(cross_repo_patterns.items(), key=lambda x: -x[1]["count"])
    gap = "Patterns principaux: " + ", ".join(f"{p}({v['count']})" for p, v in top_patterns[:3])

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_issues_collected": sum(raw_counts.values()),
        "total_relevant": len(all_classified_all),
        "by_repo": by_repo,
        "cross_repo_patterns": cross_repo_patterns,
        "top_signal_issues": top_signal_out,
        "canary_validation": {
            "issues_directly_validating_canary": core_count,
            "gap_identified": gap,
        },
    }

    with open(DATA_DIR / "patterns_summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── Update collection_log ────────────────────────────────────────────────
    log["issues_per_repo_totals"] = raw_counts
    log["total_new_raw"] = total_new_raw
    log["total_new_classified"] = total_new_classified

    with open(DATA_DIR / "collection_log.json", "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\n=== DONE ===", file=sys.stderr)
    print(f"New raw issues: {total_new_raw}", file=sys.stderr)
    print(f"New classified issues: {total_new_classified}", file=sys.stderr)
    print(f"Total raw: {sum(raw_counts.values())}", file=sys.stderr)
    print(f"Total classified: {len(all_classified_all)}", file=sys.stderr)
    print(f"API calls made: {log['api_calls_made']}", file=sys.stderr)


if __name__ == "__main__":
    main()
