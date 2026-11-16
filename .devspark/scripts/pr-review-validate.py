# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
"""Deterministic consistency checks for a written PR review.

Usage: python pr-review-validate.py REVIEW.md [--repo-root DIR] [--range BASE...HEAD]

Prints {"ok": bool, "issues": [{"code", "message"}]} and exits 1 when any issue is found.
With --range the risk digest is recomputed from git so the rating, report form and pasted
tables can be checked as well. Checks only what can be decided mechanically: frontmatter vs body,
recommendation vs open blocking findings, and risk never lowered.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

RATING_ORDER = {"low": 0, "medium": 1, "high": 2}
REQUIRED_KEYS = (
    "pr",
    "devspark_version",
    "reviewed_commit",
    "revision",
    "findings",
    "max_severity",
    "risk_rating",
    "risk_escalated",
)
ROW = re.compile(r"^\|\s*(?P<id>C|H|M|L|CON|PRD\d)-(?P<n>\d+)\s*\|\s*(?P<status>[^|]*)\|", re.M)
CLOSED = re.compile(r"resolved|withdrawn", re.I)


def _load_risk_engine():
    path = Path(__file__).resolve().parent / "pr-risk.py"
    spec = importlib.util.spec_from_file_location("pr_risk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_review_state_engine():
    path = Path(__file__).resolve().with_name("pr-review-state.py")
    spec = importlib.util.spec_from_file_location("pr_review_state", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load shared PR review-state engine.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, text
    return (data if isinstance(data, dict) else {}), parts[2]


def finding_rows(body: str) -> list[tuple[str, str, str]]:
    """(kind, full id, status) for every finding table row; kind is C/H/M/L/CON/PRD."""
    rows = []
    for m in ROW.finditer(body):
        kind = "PRD" if m["id"].startswith("PRD") else m["id"]
        rows.append((kind, f"{m['id']}-{m['n']}", m["status"].strip()))
    return rows


def recommendation(body: str) -> str | None:
    m = re.search(r"^## Approval Decision\s+\*\*Recommendation\*\*:\s*(.+)$", body, re.M)
    if not m:
        return None
    line = m.group(1).upper()
    for key, label in (("REQUEST CHANGES", "request-changes"), ("REJECT", "reject"), ("APPROVE", "approve")):
        if key in line:
            return label
    return None


def recompute_digest(repo_root: Path, diff_range: str) -> dict | None:
    engine = _load_risk_engine()
    try:
        names = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", diff_range],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    if not names:
        return None
    stats = engine.git_stats(repo_root, diff_range)
    return engine.build_digest(
        names,
        engine._load_overrides(repo_root),
        sum(s.get("added", 0) for s in stats.values()),
        sum(s.get("deleted", 0) for s in stats.values()),
        stats,
        engine.resolve_knowledge(repo_root),
    )


def validate(text: str, digest: dict | None = None) -> list[dict]:
    issues: list[dict] = []

    def add(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    fm, body = split_frontmatter(text)
    missing = [k for k in REQUIRED_KEYS if k not in fm]
    if missing:
        add("frontmatter-missing", f"frontmatter lacks: {', '.join(missing)}")
        return issues

    state_engine = None
    state = None
    unmet_conditions: list = []
    if "review_state" in fm:
        state_engine = _load_review_state_engine()
        try:
            state = state_engine._validate_record(fm["review_state"])
        except state_engine.StateError as exc:
            add(exc.issue["code"], exc.issue["message"])
        else:
            derived = state_engine._derive(state)
            unmet_conditions = derived["unmet_conditions"]
            try:
                rendered = state_engine._render_views(body, state)
            except state_engine.StateError as exc:
                add(exc.issue["code"], exc.issue["message"])
            else:
                if rendered != body:
                    add("derived-view-mismatch", "Generated review sections do not match the authoritative review_state.")
            declared_historical = fm.get("historical_findings")
            if declared_historical != fm.get("findings"):
                add("historical-counts", "findings must remain the labeled unique historical totals.")
            if fm.get("current_findings") != derived["current_counts"]:
                add("current-counts", "current_findings do not match the active authoritative findings.")
            if fm.get("current_state_counts") != derived["current_state_counts"]:
                add("current-state-counts", "current_state_counts do not match the authoritative lifecycle states.")
            if fm.get("unresolved_blockers") != derived["unresolved_blockers"]:
                add("unresolved-blockers", "unresolved_blockers does not match review_state.")
            if fm.get("recommendation") != derived["recommendation"]:
                add("recommendation", "recommendation does not match current blockers and review conditions.")
            if fm.get("gate_status") != derived["gate_status"]:
                add("gate-status", "gate_status does not match applicable review conditions.")
            expected_counts = {
                severity: sum(finding["severity"] == severity for finding in state["findings"])
                for severity in ("critical", "high", "medium", "low")
            }
            expected_counts["con"] = sum(finding.get("category") == "constitution" for finding in state["findings"])
            if fm.get("findings") != expected_counts:
                add("historical-counts", "Historical severity counts do not match unique canonical findings.")
            expected_max = next((severity for severity in ("critical", "high", "medium", "low")
                                 if expected_counts[severity]), "none")
            if fm.get("max_severity") != expected_max:
                add("max-severity", f"max_severity is {fm.get('max_severity')} but review_state implies {expected_max}")

    rows = finding_rows(body)
    counts = fm.get("findings") or {}
    if state is None and fm.get("revision") == 1:
        raised = {k: len({fid for kind, fid, _ in rows if kind == label}) for k, label in
                  (("critical", "C"), ("high", "H"), ("medium", "M"), ("low", "L"), ("con", "CON"))}
        for key, value in raised.items():
            if counts.get(key) != value:
                add("findings-count", f"frontmatter findings.{key}={counts.get(key)} but the body has {value}")

    present = [s for s in ("critical", "high", "medium", "low") if counts.get(s)]
    expected_max = present[0] if present else "none"
    if fm.get("max_severity") != expected_max:
        add("max-severity", f"max_severity is {fm.get('max_severity')} but counts imply {expected_max}")

    if state is not None:
        blocking_open = [
            finding["finding_id"] for finding in state["findings"]
            if finding["blocking"] and finding["status"] != "resolved" and not finding.get("disposition")
        ]
    else:
        blocking_open = [
            fid for kind, fid, status in rows if kind in ("C", "H", "PRD") and not CLOSED.search(status)
        ]
    rec = recommendation(body)
    # An unmet required review condition is a legitimate, state-engine-derived reason to request changes.
    if rec in ("request-changes", "reject") and not blocking_open and not unmet_conditions:
        add("rec-without-blocker",
            "REQUEST CHANGES/REJECT needs at least one open blocking finding (C, H or PRD) or an unmet required condition")
    if rec == "approve" and blocking_open:
        add("approve-with-blocker", f"APPROVE while blocking findings are open: {', '.join(blocking_open[:5])}")
    immediate = re.search(r"### Immediate Actions[^\n]*\n(.*?)(?=\n### |\n## )", body, re.S)
    if immediate:
        says_none = "None found" in immediate.group(1)
        if says_none and blocking_open:
            add("immediate-actions", "Immediate Actions says none, but blocking findings are open")
        if not says_none and not blocking_open:
            add("immediate-actions", "Immediate Actions lists items, but no blocking finding is open")

    if digest:
        floor = digest["rating"]
        rating = fm.get("risk_rating")
        if rating not in RATING_ORDER or RATING_ORDER[rating] < RATING_ORDER[floor]:
            add("risk-lowered", f"risk_rating {rating} is below the computed floor {floor}")
        elif (rating != floor) != bool(fm.get("risk_escalated")):
            add("risk-escalation-flag", "risk_escalated must be true exactly when risk_rating exceeds the computed rating")
        if digest["report_form"] == "short" and "## Changed Files" in body:
            add("form-bloat", "short report form must not include the Changed Files section")
        if digest["report_form"] != "short" and digest["tables"]["changed_files"].splitlines()[0] not in body:
            add("table-not-pasted", "the script-generated Changed Files table is missing")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--range", dest="diff_range", default="")
    args = parser.parse_args(argv)

    text = Path(args.review).read_text(encoding="utf-8")
    digest = recompute_digest(Path(args.repo_root), args.diff_range) if args.diff_range else None
    issues = validate(text, digest)
    json.dump({"ok": not issues, "issues": issues}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
