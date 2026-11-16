# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
"""Read, validate, and update the authoritative PR review finding state."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

FORMAT_VERSION = 1
ID_RE = re.compile(r"(?P<kind>CON|PRD\d+|C|H|M|L)-(?P<number>\d{2,})", re.I)
ACTION_RE = re.compile(r"^\s*-\s*\[(?P<checked>[ xX])\]\s+\*\*(?P<ids>[^*]+)\*\*\s*(?P<rest>.*)$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
FRONTMATTER_MARKER_RE = re.compile(r"(?m)^review_state\s*:")
CLOSED_RE = re.compile(r"\b(resolved|closed|withdrawn|legacy\s+resolved)\b", re.I)


class StateError(Exception):
    def __init__(self, code: str, message: str, location: str, recovery: str = "") -> None:
        super().__init__(message)
        self.issue = {
            "code": code,
            "message": message,
            "location": location,
            "recovery": recovery,
        }


def _frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    if not text.startswith("---"):
        return {}, text, False
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise StateError("malformed-record", "Review frontmatter is not terminated.", "frontmatter")
    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise StateError("malformed-record", "Review frontmatter is not valid YAML.", "frontmatter") from exc
    if not isinstance(metadata, dict):
        raise StateError("malformed-record", "Review frontmatter must be a mapping.", "frontmatter")
    return metadata, parts[2], True


def _split_ids(value: str, location: str) -> tuple[str, list[str], str, str]:
    matches = list(ID_RE.finditer(value))
    if not matches:
        raise StateError("malformed-finding", "Finding-like entry has no supported identifier.", location,
                         "Correct the identifier or explicitly resolve the unsupported entry.")
    ids = [f"{m['kind'].upper()}-{m['number']}" for m in matches]
    # Only explicit slash-joined identifiers establish alias identity.
    pieces = re.split(r"\s*/\s*", value.strip())
    if len(pieces) > 1 and len(ids) != len(pieces):
        raise StateError("malformed-finding", "Combined finding identifier is malformed.", location,
                         "Correct the explicit alias pair or resolve the entry manually.")
    canonical = ids[0]
    aliases = ids[1:] if len(pieces) > 1 else []
    severity_kind = next((m["kind"].upper() for m in matches if m["kind"].upper() in {"C", "H", "M", "L"}), "")
    category = next((m["kind"].upper() for m in matches if m["kind"].upper().startswith("PRD")), None)
    if severity_kind:
        severity = {"C": "critical", "H": "high", "M": "medium", "L": "low"}[severity_kind]
    elif category:
        severity = "medium"
    elif canonical.startswith("CON-"):
        severity = "medium"
        category = "constitution"
    else:
        raise StateError("missing-classification", "Finding identifier does not establish a supported severity.", location,
                         "Provide an explicit severity classification or resolve the legacy entry.")
    return canonical, aliases, severity, category or ""


def _visible_lines(body: str) -> list[tuple[int, str]]:
    visible: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            visible.append((number, line))
    return visible


def _legacy_findings(body: str, recovery_target: str | None = None) -> list[dict[str, Any]]:
    lines = _visible_lines(body)
    rows: list[dict[str, Any]] = []
    section = ""
    table_headers: list[str] | None = None
    in_table = False
    for index, (line_number, line) in enumerate(lines):
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            table_headers = None
            in_table = False
        action = ACTION_RE.match(line)
        if action:
            location = f"line {line_number}"
            canonical, aliases, severity, category = _split_ids(action["ids"], location)
            summary = action["rest"].strip()
            summary = re.sub(r"^`[^`]*`\s*[—-]\s*", "", summary)
            rows.append({
                "finding_id": canonical, "aliases": aliases, "severity": severity,
                "category": category or None, "blocking": _section_blocking(section),
                "description": summary, "expected_outcome": "", "evidence": [],
                "recommended_action": "", "execution_mode": "manual",
                "status": "resolved" if action["checked"].strip() else "open",
                "outcome": "Legacy resolved" if action["checked"].strip() else "",
                "provenance": {
                    "kind": "legacy", "location": location, "section": section, "line": line,
                    "basis": "checked action item" if action["checked"].strip() else "unchecked action item",
                },
                "remediation": None, "verification": None, "disposition": None, "reopen_reason": None,
            })
        if line.lstrip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if table_headers is None and cells and cells[0].lower() in {"id", "finding", "finding id"}:
                table_headers = [cell.lower() for cell in cells]
                in_table = True
                continue
            if TABLE_SEPARATOR_RE.match(line):
                continue
            if in_table and table_headers and len(cells) >= 2:
                id_value = cells[0]
                if not ID_RE.search(id_value):
                    continue
                location = f"line {line_number}"
                canonical, aliases, severity, category = _split_ids(id_value, location)
                values = {header: cells[pos] for pos, header in enumerate(table_headers) if pos < len(cells)}
                status = values.get("status", "")
                description = values.get("issue", values.get("description", ""))
                fix = values.get("fix", values.get("action", ""))
                closed = bool(CLOSED_RE.search(status))
                evidence = [values[key] for key in ("principle", "file:line", "file") if values.get(key)]
                rows.append({
                    "finding_id": canonical, "aliases": aliases, "severity": severity,
                    "category": category or None, "blocking": _section_blocking(section),
                    "description": description, "expected_outcome": fix, "evidence": evidence,
                    "recommended_action": fix, "execution_mode": "manual",
                    "status": "resolved" if closed else "open",
                    "outcome": "Legacy resolved" if closed else "",
                    "provenance": {
                        "kind": "legacy", "location": location, "section": section, "line": line,
                        "basis": status or "detail table",
                    },
                    "remediation": None, "verification": None, "disposition": None, "reopen_reason": None,
                })
        elif in_table and line.strip() and not line.lstrip().startswith("|"):
            in_table = False
            table_headers = None

    if not rows:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    alias_owner: dict[str, str] = {}
    for row in rows:
        canonical = row["finding_id"]
        for alias in row["aliases"]:
            prior_owner = alias_owner.get(alias)
            if prior_owner and prior_owner != canonical:
                if recovery_target not in {prior_owner, canonical}:
                    raise StateError("alias-conflict", f"Alias {alias} belongs to multiple findings.",
                                     row["provenance"]["location"], "Choose the canonical finding that owns this alias.")
                if canonical == recovery_target:
                    alias_owner[alias] = canonical
            else:
                alias_owner[alias] = canonical
    if recovery_target is not None:
        for row in rows:
            row["aliases"] = [
                alias for alias in row["aliases"]
                if alias_owner.get(alias) == row["finding_id"]
            ]
    by_id.clear()
    alias_owner.clear()
    for row in rows:
        canonical = row["finding_id"]
        for alias in row["aliases"]:
            prior_owner = alias_owner.get(alias)
            if prior_owner and prior_owner != canonical:
                raise StateError("alias-conflict", f"Alias {alias} belongs to multiple findings.",
                                 row["provenance"]["location"], "Choose the canonical finding that owns this alias.")
            alias_owner[alias] = canonical
        prior = by_id.get(canonical)
        if prior is None:
            by_id[canonical] = row
            continue
        if prior["status"] != row["status"]:
            if canonical == recovery_target:
                continue
            raise StateError("contradictory-legacy-status", f"Finding {canonical} has conflicting action/table status.",
                             row["provenance"]["location"], "Resolve the conflicting legacy status without inferring closure.")
        if prior["blocking"] is None:
            prior["blocking"] = row["blocking"]
        elif row["blocking"] is not None and prior["blocking"] != row["blocking"]:
            if canonical == recovery_target:
                prior["blocking"] = True
            else:
                raise StateError(
                    "contradictory-legacy-blocking",
                    f"Finding {canonical} has conflicting blocking classifications.",
                    row["provenance"]["location"],
                    "Use recover-legacy with an authorized, evidence-based interpretation.",
                )
        if prior["aliases"] != row["aliases"] and prior["aliases"] and row["aliases"]:
            if canonical == recovery_target:
                continue
            raise StateError("alias-conflict", f"Finding {canonical} has conflicting aliases.",
                             row["provenance"]["location"], "Choose the explicit alias set for this finding.")
        if row["aliases"]:
            prior["aliases"] = row["aliases"]
        if row["description"]:
            if prior["description"] and prior["description"] != row["description"]:
                # Different table/action renderings can carry different amounts of context;
                # keep the more complete source rather than treating prose variation as identity.
                prior["description"] = max((prior["description"], row["description"]), key=len)
            else:
                prior["description"] = row["description"]
        if row["expected_outcome"]:
            prior["expected_outcome"] = row["expected_outcome"]
            prior["recommended_action"] = row["recommended_action"]
        if row["status"] == "resolved":
            prior["provenance"] = row["provenance"]
    for canonical, finding in by_id.items():
        if finding["blocking"] is None:
            if canonical == recovery_target:
                finding["blocking"] = True
            else:
                raise StateError(
                    "ambiguous-legacy-blocking",
                    f"Finding {canonical} has no explicit blocking classification.",
                    finding["provenance"]["location"],
                    "Use recover-legacy with a complete interpretation, evidence, reason, and named authorized reviewer.",
                )
    return list(by_id.values())


def _section_blocking(section: str) -> bool | None:
    normalized = section.lower()
    if (
        "non-blocking" in normalized
        or "nonblocking" in normalized
        or "recommended improvement" in normalized
        or "suggestion" in normalized
        or "low priority improvement" in normalized
    ):
        return False
    if "blocking" in normalized or "immediate action" in normalized:
        return True
    return None


def _validate_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise StateError("malformed-record", "review_state must be a mapping.", "review_state")
    version = record.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FORMAT_VERSION:
        raise StateError("unsupported-version", f"Unsupported review_state format version: {version!r}.",
                         "review_state.format_version", "Use a supported record version or retain the file unchanged.")
    findings = record.get("findings")
    if not isinstance(findings, list):
        raise StateError("malformed-record", "review_state.findings must be a list.", "review_state.findings")
    seen: set[str] = set()
    owners: dict[str, str] = {}
    if not isinstance(record.get("conditions", []), list):
        raise StateError("malformed-record", "review_state.conditions must be a list.", "review_state.conditions")
    required = ("finding_id", "aliases", "severity", "category", "blocking", "description",
                "expected_outcome", "evidence", "recommended_action", "execution_mode", "status",
                "outcome", "provenance", "remediation", "verification", "disposition", "reopen_reason")
    for index, finding in enumerate(findings):
        location = f"review_state.findings[{index}]"
        if not isinstance(finding, dict) or any(key not in finding for key in required):
            raise StateError("malformed-record", "A structured finding is missing required fields.", location)
        fid = finding["finding_id"]
        if not isinstance(fid, str) or not ID_RE.fullmatch(fid):
            raise StateError("malformed-record", "finding_id is not a supported canonical identifier.", location)
        if fid in seen:
            raise StateError("identity-conflict", f"Duplicate canonical finding {fid}.", location)
        seen.add(fid)
        if not isinstance(finding["severity"], str) or finding["severity"] not in {"critical", "high", "medium", "low"}:
            raise StateError("missing-classification", f"Finding {fid} has an invalid severity.", location)
        if finding["category"] is not None and not isinstance(finding["category"], str):
            raise StateError("missing-classification", f"Finding {fid} has an invalid category.", location)
        if not isinstance(finding["blocking"], bool):
            raise StateError("missing-classification", f"Finding {fid} needs explicit blocking classification.", location)
        if not isinstance(finding["status"], str) or finding["status"] not in {
                "open", "remediated", "awaiting-verification", "resolved", "reopened"}:
            raise StateError("malformed-record", f"Finding {fid} has an invalid lifecycle state.", location)
        for field in ("description", "expected_outcome", "recommended_action", "execution_mode", "outcome"):
            if not isinstance(finding[field], str):
                raise StateError("malformed-record", f"Finding {fid} has an invalid {field}.", location)
        if not isinstance(finding["evidence"], list) or not all(isinstance(item, str) for item in finding["evidence"]):
            raise StateError("malformed-record", f"Finding {fid} has malformed evidence.", location)
        if finding["status"] == "resolved":
            provenance = finding.get("provenance")
            legacy_closed = provenance == "legacy" or (
                isinstance(provenance, dict) and provenance.get("kind") == "legacy"
            )
            verification = finding.get("verification")
            if not legacy_closed and (
                not isinstance(verification, dict) or verification.get("conclusion") != "confirmed"
            ):
                raise StateError("malformed-record", f"Resolved finding {fid} lacks independent confirmation.", location)
        if finding["status"] == "reopened" and (not finding.get("reopen_reason") or not finding.get("prior_resolution")):
            raise StateError("malformed-record", f"Reopened finding {fid} must retain its prior resolution and reason.", location)
        aliases = finding["aliases"]
        if not isinstance(aliases, list) or not all(isinstance(alias, str) and ID_RE.fullmatch(alias) for alias in aliases):
            raise StateError("malformed-record", f"Finding {fid} has malformed aliases.", location)
        if len(set(aliases)) != len(aliases):
            raise StateError("alias-conflict", f"Finding {fid} repeats an alias.", location)
        if fid in owners:
            raise StateError("alias-conflict", f"Canonical finding {fid} is already owned as an alias.", location)
        for alias in aliases:
            if alias == fid or alias in seen or (alias in owners and owners[alias] != fid):
                raise StateError("alias-conflict", f"Alias {alias} is not uniquely owned.", location,
                                 "Choose one canonical owner and retain only explicit alias relationships.")
            owners[alias] = fid
    record.setdefault("conditions", [])
    for index, condition in enumerate(record["conditions"]):
        if not isinstance(condition, dict) or not isinstance(condition.get("condition_id"), str) or not condition["condition_id"]:
            raise StateError("malformed-record", "Review condition needs a stable identifier.",
                             f"review_state.conditions[{index}]")
        if condition.get("result") not in {
                "pass", "fail", "pending", "not-applicable"}:
            raise StateError("malformed-record", "Review condition has an invalid result.",
                             f"review_state.conditions[{index}]")
        if not isinstance(condition.get("required", True), bool):
            raise StateError("malformed-record", "Review condition required flag must be boolean.",
                             f"review_state.conditions[{index}].required")
        if not isinstance(condition.get("evidence", []), list) or not all(
                isinstance(item, str) for item in condition.get("evidence", [])):
            raise StateError("malformed-record", "Review condition evidence must be a string list.",
                             f"review_state.conditions[{index}].evidence")
        if not isinstance(condition.get("reason", ""), str):
            raise StateError("malformed-record", "Review condition reason must be text.",
                             f"review_state.conditions[{index}].reason")
    record.setdefault("last_change", {})
    if not isinstance(record["last_change"], dict):
        raise StateError("malformed-record", "review_state.last_change must be a mapping.", "review_state.last_change")
    return record


def _load(path: Path, recovery_target: str | None = None) -> tuple[dict[str, Any], str, str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateError("malformed-record", "Review file is not valid UTF-8.", "file") from exc
    try:
        metadata, body, has_frontmatter = _frontmatter(text)
    except StateError:
        if FRONTMATTER_MARKER_RE.search(text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else text):
            raise
        raise
    digest = hashlib.sha256(raw).hexdigest()
    if "review_state" in metadata:
        record = _validate_record(copy.deepcopy(metadata["review_state"]))
        return record, body, digest
    legacy = _legacy_findings(body, recovery_target=recovery_target)
    record = {
        "format_version": FORMAT_VERSION,
        "findings": legacy,
        "conditions": [],
        "last_change": {"operation": "legacy-read", "affected": [item["finding_id"] for item in legacy]},
    }
    return record, body, digest


def _compatibility_finding(finding: dict[str, Any]) -> dict[str, Any]:
    severity = finding["severity"]
    category = finding.get("category")
    prefix = finding["finding_id"].split("-", 1)[0]
    severity_code = prefix if prefix in {"C", "H", "M", "L", "CON"} else "PRD" if prefix.startswith("PRD") else prefix
    state = finding["status"]
    disposition = finding.get("disposition")
    if state == "resolved" or disposition:
        status = "closed"
    elif state in {"remediated", "awaiting-verification"}:
        status = "partial"
    else:
        status = "open"
    constitution = severity_code == "CON" or category == "constitution"
    provenance_value = finding.get("provenance")
    legacy_nonauto = (
        isinstance(provenance_value, dict)
        and provenance_value.get("kind") == "legacy"
        and re.search(r"accepted|deferred|waived|withdrawn|wontfix|won't fix|already fixed upstream",
                      finding.get("description", ""), re.IGNORECASE)
    )
    eligible = (
        status == "open"
        and not disposition
        and not legacy_nonauto
        and finding["blocking"]
        and (severity in {"critical", "high"} or str(category or "").startswith("PRD"))
        and not constitution
    )
    route = "evolve-constitution" if constitution else "auto" if eligible else "report"
    reason = (
        "Constitution findings route to /devspark-evolve-constitution, not to product code."
        if constitution else
        "The legacy report records an accepted, deferred or withdrawn disposition."
        if legacy_nonauto else
        f"Status is {status}; a human decides whether it still needs work."
        if status != "open" else
        "The finding records an accepted, deferred or withdrawn disposition."
        if disposition else
        f"Open {severity.title()} finding."
        if eligible and severity in {"critical", "high"} else
        "Open blocking PR-delta finding."
        if eligible else
        "Ordinary Medium or Low findings are report-only."
    )
    provenance = provenance_value if isinstance(provenance_value, dict) else {}
    match = re.search(r"\bline (\d+)\b", str(provenance.get("location", "")))
    return {
        "id": finding["finding_id"],
        "severity": severity_code,
        "severity_level": severity,
        "category": category,
        "aliases": finding["aliases"],
        "line_number": int(match.group(1)) if match else None,
        "line": provenance.get("line", ""),
        "section": provenance.get("section", ""),
        "status": status,
        "lifecycle_state": state,
        "blocking": finding["blocking"],
        "auto_eligible": eligible,
        "route": route,
        "reason": reason,
    }


def _derive(record: dict[str, Any]) -> dict[str, Any]:
    findings = record["findings"]
    active = [f for f in findings if f["status"] not in {"resolved"} and not f.get("disposition")]
    pending = [f for f in active if f["status"] == "awaiting-verification"]
    blockers = [f for f in active if f["blocking"]]
    conditions = record.get("conditions", [])
    unmet = [
        c for c in conditions
        if isinstance(c, dict) and c.get("required", True) and c.get("result") not in {"pass", "not-applicable"}
    ]
    recommendation = "request-changes" if blockers or unmet else "approve"
    compatibility_findings = [_compatibility_finding(finding) for finding in active]
    current_counts = {
        state: sum(finding["status"] == state and not finding.get("disposition") for finding in findings)
        for state in ("open", "remediated", "awaiting-verification", "reopened", "resolved")
    }
    severity_counts = {
        severity: sum(
            finding["severity"] == severity and finding["status"] != "resolved" and not finding.get("disposition")
            for finding in findings
        )
        for severity in ("critical", "high", "medium", "low")
    }
    return {
        "findings": findings,
        "historical_count": len(findings),
        "current_counts": severity_counts,
        "current_state_counts": current_counts,
        "open_findings": compatibility_findings,
        "open_count": len(compatibility_findings),
        "auto_eligible_count": sum(finding["auto_eligible"] for finding in compatibility_findings),
        "pending_verification": pending,
        "pending_verification_count": len(pending),
        "unresolved_blockers": len(blockers),
        "unmet_conditions": unmet,
        "gate_status": "fail" if any(c.get("result") == "fail" for c in unmet) else "pending" if unmet else "pass",
        "recommendation": recommendation,
        "diagnostics": [],
    }


def inspect(path: Path, pr_id: int | None = None) -> dict[str, Any]:
    record, _body, digest = _load(path)
    return {
        "ok": True, "pr_id": pr_id,
        "review_file": str(path),
        "record": record, "digest": digest, **_derive(record),
    }


def _acquire_guard(path: Path) -> Path:
    guard = path.with_name(f".{path.name}.lock")
    try:
        fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StateError("writer-busy", "Another writer holds the review update guard.", str(path),
                         "Confirm no update is active; remove only a confirmed stale guard.") from exc
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(f"{os.getpid()}\n")
    return guard


def _atomic_write(path: Path, content: bytes, expected_digest: str) -> str:
    lock = _acquire_guard(path)
    temporary: Path | None = None
    try:
        current = path.read_bytes()
        actual = hashlib.sha256(current).hexdigest()
        if actual != expected_digest:
            raise StateError("stale-record", "Review changed after it was inspected.", str(path),
                             "Re-read the current record and repeat the bounded operation.")
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        return hashlib.sha256(content).hexdigest()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def _dump_review(metadata: dict[str, Any], body: str) -> bytes:
    front = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n{body.lstrip()}".encode("utf-8")


STATE_REGIONS = {
    "action": ("<!-- PR-REVIEW-DERIVED:ACTION:BEGIN -->", "<!-- PR-REVIEW-DERIVED:ACTION:END -->", "Action Items"),
    "detail": ("<!-- PR-REVIEW-DERIVED:DETAIL:BEGIN -->", "<!-- PR-REVIEW-DERIVED:DETAIL:END -->", "Findings Detail"),
    "decision": ("<!-- PR-REVIEW-DERIVED:DECISION:BEGIN -->", "<!-- PR-REVIEW-DERIVED:DECISION:END -->", "Approval Decision"),
    "summary": ("<!-- PR-REVIEW-DERIVED:SUMMARY:BEGIN -->", "<!-- PR-REVIEW-DERIVED:SUMMARY:END -->", "Current Review State"),
}


def _ensure_state_regions(body: str) -> str:
    for name, (begin, end, heading) in STATE_REGIONS.items():
        begin_count, end_count = body.count(begin), body.count(end)
        if begin_count == 1 and end_count == 1:
            if body.index(end) < body.index(begin):
                raise StateError("malformed-derived-boundary", f"The {name} derived-state markers are out of order.",
                                 "body", "Restore the generated-state markers in begin/end order.")
            continue
        if begin_count or end_count:
            raise StateError("malformed-derived-boundary", f"The {name} derived-state marker pair is incomplete or duplicated.",
                             "body", "Restore exactly one matching generated-state marker pair.")
        heading_pattern = re.compile(rf"(?m)^## {re.escape(heading)}\s*$")
        match = heading_pattern.search(body)
        if match is None:
            body = body.rstrip() + f"\n\n{begin}\n## {heading}\n{end}\n"
            continue
        if heading_pattern.search(body, match.end()):
            raise StateError("malformed-derived-boundary", f"Review contains multiple {heading} sections.",
                             "body", "Resolve duplicate generated sections before updating state.")
        next_heading = re.search(r"(?m)^##\s+", body[match.end():])
        region_end = match.end() + next_heading.start() if next_heading else len(body)
        if heading == "Approval Decision":
            separator = re.search(r"(?m)^---\s*$", body[match.end():])
            if separator:
                region_end = min(region_end, match.end() + separator.start())
        body = (
            body[:match.start()] + begin + "\n" + body[match.start():region_end].rstrip()
            + "\n" + end + "\n" + body[region_end:]
        )
    return body


def _replace_state_region(body: str, name: str, content: str) -> str:
    begin, end, _heading = STATE_REGIONS[name]
    if body.count(begin) != 1 or body.count(end) != 1:
        raise StateError("malformed-derived-boundary", f"Review must contain exactly one {name} derived-state marker pair.",
                         "body", "Restore the generated-state markers without removing reviewer narrative or evidence.")
    start = body.index(begin)
    end_at = body.index(end)
    if end_at <= start:
        raise StateError("malformed-derived-boundary", f"The {name} derived-state markers are out of order.",
                         "body", "Restore the generated-state markers in begin/end order.")
    return body[:start + len(begin)] + "\n" + content.strip() + "\n" + body[end_at:]


def _render_views(body: str, record: dict[str, Any]) -> str:
    findings = record["findings"]
    derived = _derive(record)
    body = _ensure_state_regions(body)
    action_lines = ["## Action Items", "", "### Immediate Actions (Blocking)", ""]
    blockers = [f for f in findings if f["blocking"] and f["status"] != "resolved" and not f.get("disposition")]
    for finding in blockers:
        aliases = f" / {' / '.join(finding['aliases'])}" if finding["aliases"] else ""
        state_label = {
            "open": "Open", "remediated": "Remediated; awaiting submission",
            "awaiting-verification": "Pending independent verification", "reopened": "Reopened",
        }[finding["status"]]
        action_lines.append(f"- [ ] **{finding['finding_id']}{aliases}** [{state_label}] — {finding['description']}")
    if not blockers:
        action_lines.append("- None found.")
    action_lines.extend(["", "### Recommended Improvements", ""])
    recommendations = [f for f in findings if not f["blocking"] and f["status"] != "resolved" and
                       not f.get("disposition") and not f["finding_id"].startswith("CON-")]
    action_lines.extend(
        [f"- [ ] **{f['finding_id']}** [{f['status']}] — {f['description']}" for f in recommendations]
        if recommendations else ["- None."]
    )
    constitution = [f for f in findings if f["finding_id"].startswith("CON-") and f["status"] != "resolved" and
                    not f.get("disposition")]
    action_lines.extend(["", "### Constitution Improvements", ""])
    action_lines.extend(
        [f"- [ ] **{f['finding_id']}** — {f['description']}" for f in constitution]
        if constitution else ["- None."]
    )
    dispositions = [f for f in findings if f.get("disposition")]
    if dispositions:
        action_lines.extend(["", "### Governed Dispositions", ""])
        for finding in dispositions:
            value = finding["disposition"]
            action_lines.append(
                f"- **{finding['finding_id']}** — {value['kind'].title()}: {value['reason']} "
                f"(authority: {value['authorized_by']}; capture: {value['capture_reference']})"
            )
    body = _replace_state_region(body, "action", "\n".join(action_lines))

    detail_lines = ["## Findings Detail", "", "| ID | Status | Severity | Blocking | Issue | Expected outcome | Evidence |",
                    "| --- | --- | --- | --- | --- | --- | --- |"]
    for finding in findings:
        aliases = f" / {' / '.join(finding['aliases'])}" if finding["aliases"] else ""
        if finding.get("disposition"):
            status = f"{finding['disposition']['kind'].title()} disposition"
        else:
            status = {
                "open": "Open", "remediated": "Remediated",
                "awaiting-verification": "Pending verification",
                "resolved": "Resolved — independently verified" if finding.get("verification") else "Legacy resolved",
                "reopened": "Reopened",
            }[finding["status"]]
        description = finding["description"].replace("|", "\\|").replace("\n", " ")
        expected = finding["expected_outcome"].replace("|", "\\|").replace("\n", " ")
        evidence = "; ".join(finding["evidence"]).replace("|", "\\|").replace("\n", " ")
        detail_lines.append(
            f"| {finding['finding_id']}{aliases} | {status} | {finding['severity']} | "
            f"{'Yes' if finding['blocking'] and not finding.get('disposition') else 'No'} | "
            f"{description} | {expected} | {evidence} |"
        )
    body = _replace_state_region(body, "detail", "\n".join(detail_lines))

    summary_lines = [
        "## Current Review State", "",
        f"- Historical unique findings: {derived['historical_count']}",
        f"- Current unresolved findings by severity: {derived['current_counts']}",
        f"- Current lifecycle state counts: {derived['current_state_counts']}",
        f"- Unresolved blockers: {derived['unresolved_blockers']}",
        f"- Pending independent verification: {derived['pending_verification_count']}",
        f"- Review conditions: {derived['gate_status']}",
        f"- Local recommendation: {derived['recommendation']}",
    ]
    body = _replace_state_region(body, "summary", "\n".join(summary_lines))
    decision_lines = [
        "## Approval Decision", "",
        f"**Recommendation**: {derived['recommendation'].replace('-', ' ').upper()} — derived from current blockers and applicable review conditions.",
        "",
        "*This local recommendation does not cast a hosted approval vote or authorize merge.*",
    ]
    return _replace_state_region(body, "decision", "\n".join(decision_lines))


def _update_metadata(metadata: dict[str, Any], record: dict[str, Any]) -> None:
    findings = record["findings"]
    derived = _derive(record)
    counts = {severity: sum(f["severity"] == severity for f in findings)
              for severity in ("critical", "high", "medium", "low")}
    counts["con"] = sum(f.get("category") == "constitution" for f in findings)
    metadata["findings"] = counts
    metadata["historical_findings"] = counts
    metadata["current_findings"] = derived["current_counts"]
    metadata["current_state_counts"] = derived["current_state_counts"]
    metadata["unresolved_blockers"] = derived["unresolved_blockers"]
    metadata["recommendation"] = derived["recommendation"]
    metadata["gate_status"] = derived["gate_status"]
    present = [severity for severity in ("critical", "high", "medium", "low") if counts[severity]]
    metadata["max_severity"] = present[0] if present else "none"


def _find_event(record: dict[str, Any], finding_id: str) -> dict[str, Any]:
    for finding in record["findings"]:
        if finding["finding_id"] == finding_id or finding_id in finding["aliases"]:
            return finding
    raise StateError("finding-not-found", f"Finding {finding_id} does not exist.", "event.finding_id")


def _require_commit(repo_root: Path, commit: str, location: str) -> None:
    import subprocess

    if not re.fullmatch(r"[0-9a-f]{40}", str(commit), re.I):
        raise StateError("wrong-correction-context", "A full Git commit identifier is required.", location)
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=repo_root,
            capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StateError("wrong-correction-context", "Git could not inspect the correction commit.", location) from exc
    if result.returncode:
        raise StateError("wrong-correction-context", "The correction commit is not present in this repository.",
                         location, "Commit the correction in the selected repository before recording remediation.")


def _verify_git_context(event: dict[str, Any], repo_root: Path, review_path: Path) -> None:
    import subprocess

    correction = event.get("correction_commit")
    evaluated = event.get("evaluated_commit")
    if not correction or not evaluated:
        raise StateError("wrong-correction-context", "Verification must name correction and evaluated commits.",
                         "event", "Provide full commit identifiers for the correction and evaluated context.")
    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True,
                                timeout=15, stdin=subprocess.DEVNULL)
        if result.returncode:
            raise StateError("wrong-correction-context", "Git could not validate the evaluated correction context.",
                             "event", "Re-run the focused evaluation against a valid committed context.")
        return result.stdout.strip()
    try:
        git("cat-file", "-e", f"{correction}^{{commit}}")
        git("cat-file", "-e", f"{evaluated}^{{commit}}")
        git("merge-base", "--is-ancestor", correction, evaluated)
    except StateError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise StateError("wrong-correction-context", "Correction is not an ancestor of the evaluated commit.",
                         "event", "Evaluate the committed correction or provide the matching context.") from exc
    if git("rev-parse", "HEAD") != evaluated:
        raise StateError("wrong-correction-context", "The evaluated commit is not the current repository HEAD.",
                         "event.evaluated_commit", "Evaluate the current committed context and retry.")
    status = git("status", "--porcelain", "--untracked-files=all")
    try:
        allowed = review_path.resolve().relative_to(repo_root.resolve()).as_posix().replace("/", "\\")
    except ValueError as exc:
        raise StateError("wrong-correction-context", "The review file is outside the evaluated repository.",
                         "review_file") from exc
    changed = [line[3:].replace("/", "\\") for line in status.splitlines() if line[3:].replace("/", "\\") != allowed]
    if changed:
        raise StateError("wrong-correction-context", "The evaluated repository has non-review working changes.",
                         "repository", "Commit or remove unrelated changes, then repeat the focused evaluation.")


def _apply_event(record: dict[str, Any], event: dict[str, Any], repo_root: Path, review_path: Path) -> bool:
    operation = event.get("operation")
    if not isinstance(operation, str):
        raise StateError("malformed-event", "Event operation must be a string.", "event.operation")
    if "conditions" in event and operation not in {"record", "initial-review", "verify"}:
        raise StateError("unauthorized-transition", "Review conditions can be recorded only during initial review or independent evaluation.", "event.conditions")
    if operation in {"record", "initial-review"}:
        finding = event.get("finding")
        if not isinstance(finding, dict):
            raise StateError("malformed-event", "record event requires a finding mapping.", "event.finding")
        candidate = copy.deepcopy(finding)
        duplicate = next((existing for existing in record["findings"]
                          if existing["finding_id"] == candidate.get("finding_id")), None)
        if duplicate is not None:
            if duplicate == candidate:
                return False
            raise StateError("identity-conflict", f"Finding {candidate.get('finding_id')} already exists.",
                             "event.finding.finding_id", "Use the existing canonical finding or select a new identity.")
        if candidate.get("status") not in {"open", "resolved"}:
            raise StateError("unauthorized-transition", "New structured findings must start open.", "event.finding.status")
        if candidate.get("status") == "resolved" and (
            candidate.get("provenance") != "legacy" or candidate.get("verification") is not None
        ):
            raise StateError("unauthorized-transition", "New findings cannot be recorded as resolved.", "event.finding.status")
        _validate_record({**record, "findings": record["findings"] + [candidate]})
        record["findings"].append(candidate)
        if "conditions" in event:
            record["conditions"] = event["conditions"]
    else:
        finding = _find_event(record, str(event.get("finding_id", "")))
        if operation in {"remediate", "remediate-and-submit"}:
            if finding["status"] not in {"open", "reopened"}:
                raise StateError("unauthorized-transition", f"Cannot remediate finding in state {finding['status']}.", "event")
            remediation = event.get("remediation")
            if not isinstance(remediation, dict) or not all(remediation.get(k) for k in
                    ("correction_commit", "author_context", "explanation")):
                raise StateError("missing-classification", "Remediation needs a correction commit, author context, and explanation.", "event.remediation")
            if not re.fullmatch(r"[0-9a-f]{40}", str(remediation["correction_commit"]), re.I):
                raise StateError("wrong-correction-context", "Remediation must identify a full correction commit.", "event.remediation.correction_commit")
            _require_commit(repo_root, remediation["correction_commit"], "event.remediation.correction_commit")
            if not remediation.get("author_validation") and not remediation.get("author_validation_absent_reason"):
                raise StateError("missing-classification", "Record actual author validation or its explicit absence.", "event.remediation.author_validation")
            if operation == "remediate-and-submit" and not remediation.get("proof_obligation"):
                raise StateError("missing-classification", "Submission must retain the independent proof obligation.", "event.remediation.proof_obligation")
            finding["remediation"] = remediation
            finding["status"] = "awaiting-verification" if operation == "remediate-and-submit" else "remediated"
        elif operation == "submit":
            if finding["status"] != "remediated":
                raise StateError("unauthorized-transition", "Only remediated findings can be submitted.", "event")
            obligation = event.get("proof_obligation") or (finding.get("remediation") or {}).get("proof_obligation")
            if not obligation:
                raise StateError("missing-classification", "Submission must retain the independent proof obligation.", "event.proof_obligation")
            finding["remediation"]["proof_obligation"] = obligation
            finding["status"] = "awaiting-verification"
        elif operation == "verify":
            if finding["status"] != "awaiting-verification":
                raise StateError("unauthorized-transition", "Finding is not awaiting independent verification.", "event")
            evaluation = event.get("verification")
            if not isinstance(evaluation, dict) or not all(evaluation.get(k) for k in
                    ("reviewer_context", "reviewer_role", "conclusion", "proof", "rationale", "correction_commit", "evaluated_commit")):
                raise StateError("missing-classification", "Independent evaluation is missing required evidence.", "event.verification")
            if evaluation["reviewer_context"] == finding.get("remediation", {}).get("author_context"):
                raise StateError("author-self-verification", "The remediation author cannot independently verify the correction.", "event.verification")
            if evaluation["correction_commit"] != finding["remediation"].get("correction_commit"):
                raise StateError("wrong-correction-context", "Evaluation references a different correction.", "event.verification")
            _verify_git_context(evaluation, repo_root, review_path)
            finding["verification"] = evaluation
            if evaluation["conclusion"] == "confirmed":
                finding["status"] = "resolved"
                finding["outcome"] = "Independently verified"
            elif evaluation["conclusion"] == "incomplete":
                finding["status"] = "open"
                finding["outcome"] = "Independent evaluation found incomplete remediation"
            elif evaluation["conclusion"] != "inconclusive":
                raise StateError("malformed-event", "Unknown independent evaluation conclusion.", "event.verification.conclusion")
            elif evaluation["conclusion"] == "inconclusive":
                finding["outcome"] = "Independent evaluation is inconclusive"
            if "conditions" in event:
                record["conditions"] = event["conditions"]
        elif operation == "reopen":
            if finding["status"] != "resolved":
                raise StateError("unauthorized-transition", "Only resolved findings can be reopened.", "event")
            evaluation = event.get("verification")
            if not event.get("reopen_reason") or not isinstance(evaluation, dict) or not all(
                    evaluation.get(k) for k in ("reviewer_context", "reviewer_role", "conclusion", "proof",
                                                "rationale", "correction_commit", "evaluated_commit")):
                raise StateError("missing-classification", "Reopening requires substantive evidence and an evaluator.", "event")
            prior_verification = finding.get("verification") or {}
            if evaluation["reviewer_context"] in {
                    prior_verification.get("reviewer_context"),
                    (finding.get("remediation") or {}).get("author_context")}:
                raise StateError("author-self-verification", "Reopening requires a distinct evaluator.", "event.verification")
            if evaluation["conclusion"] != "incomplete":
                raise StateError("malformed-event", "Reopening evaluation must identify an incomplete or recurring correction.", "event.verification.conclusion")
            if evaluation["correction_commit"] != (finding.get("remediation") or {}).get("correction_commit"):
                raise StateError("wrong-correction-context", "Reopening evidence references a different correction.", "event.verification.correction_commit")
            _verify_git_context(evaluation, repo_root, review_path)
            finding["prior_resolution"] = {
                "outcome": finding.get("outcome", ""),
                "verification": copy.deepcopy(prior_verification),
            }
            finding["status"] = "reopened"
            finding["reopen_reason"] = event["reopen_reason"]
            finding["verification"] = evaluation
        elif operation == "disposition":
            if finding["status"] in {"resolved", "remediated", "awaiting-verification"}:
                raise StateError("unauthorized-transition", "Disposition cannot replace a resolved or in-flight correction.", "event")
            disposition = event.get("disposition")
            if not isinstance(disposition, dict) or not all(disposition.get(k) for k in
                    ("kind", "reason", "authorized_by", "capture_reference")):
                raise StateError("missing-classification", "Governed disposition needs kind, reason, authority, and capture reference.", "event.disposition")
            if disposition["kind"] not in {"accepted", "deferred", "withdrawn"}:
                raise StateError("malformed-event", "Disposition kind must be accepted, deferred, or withdrawn.", "event.disposition.kind")
            finding["disposition"] = disposition
        elif operation == "recover-legacy":
            provenance = finding.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("kind") != "legacy":
                raise StateError("unauthorized-transition", "Only legacy findings can use explicit legacy recovery.", "event")
            recovery = event.get("recovery")
            if not isinstance(recovery, dict) or not all(recovery.get(k) for k in
                    ("reason", "authorized_by", "chosen_interpretation", "evidence")):
                raise StateError("missing-classification", "Legacy recovery needs authority, selected interpretation, evidence, and reason.", "event.recovery")
            if not all(isinstance(recovery[key], str) and recovery[key].strip()
                       for key in ("reason", "authorized_by")):
                raise StateError("malformed-event", "Recovery reason and authority must be non-empty text.", "event.recovery")
            if not isinstance(recovery["evidence"], list) or not all(
                    isinstance(item, str) and item.strip() for item in recovery["evidence"]):
                raise StateError("malformed-event", "Recovery evidence must be a non-empty list of text.", "event.recovery.evidence")
            interpretation = recovery["chosen_interpretation"]
            if not isinstance(interpretation, dict):
                raise StateError("malformed-event", "Chosen legacy interpretation must be a finding mapping.", "event.recovery.chosen_interpretation")
            required_interpretation = {
                "finding_id", "aliases", "severity", "category", "blocking", "description",
                "expected_outcome", "evidence", "recommended_action", "execution_mode", "status",
                "outcome", "remediation", "verification", "disposition", "reopen_reason",
            }
            if not required_interpretation.issubset(interpretation):
                raise StateError("missing-classification", "Recovery must provide the complete selected finding interpretation.",
                                 "event.recovery.chosen_interpretation")
            if interpretation.get("finding_id") != finding["finding_id"]:
                raise StateError("identity-conflict", "Recovery must retain the selected canonical finding identity.",
                                 "event.recovery.chosen_interpretation.finding_id")
            for key in ("finding_id", "aliases", "severity", "category", "blocking", "description",
                        "expected_outcome", "evidence", "recommended_action", "execution_mode", "status",
                        "outcome", "remediation", "verification", "disposition", "reopen_reason"):
                if key in interpretation:
                    finding[key] = interpretation[key]
            finding["provenance"] = {**finding["provenance"], "recovery": recovery}
        elif operation == "render":
            return False
        else:
            raise StateError("malformed-event", f"Unsupported state operation: {operation!r}.", "event.operation")
    record["last_change"] = {
        "operation": operation,
        "affected": [event.get("finding_id", event.get("finding", {}).get("finding_id", ""))],
        "event_fingerprint": hashlib.sha256(
            json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "actor_role": event.get("actor_role", ""),
        "actor_context": event.get("actor_context", ""),
        "explanation": event.get("explanation", ""),
    }
    return True


def apply(path: Path, event_path: Path, expected_digest: str, repo_root: Path) -> dict[str, Any]:
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError("malformed-event", "Event input is not valid JSON.", str(event_path)) from exc
    if not isinstance(event, dict):
        raise StateError("malformed-event", "Event input must be a JSON object.", str(event_path))
    recovery_target = str(event.get("finding_id", "")) if event.get("operation") == "recover-legacy" else None
    record, body, digest = _load(path, recovery_target=recovery_target)
    if digest != expected_digest:
        raise StateError("stale-record", "Review changed after it was inspected.", str(path))
    fingerprint = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if record.get("last_change", {}).get("event_fingerprint") == fingerprint:
        return {"ok": True, "changed": False, "revision": None, "record_digest": digest, **_derive(record)}
    before = copy.deepcopy(record)
    changed = _apply_event(record, event, repo_root, path)
    if not changed or record == before:
        return {"ok": True, "changed": False, "revision": None, "record_digest": digest, **_derive(record)}
    _validate_record(record)
    record["last_change"]["actor_role"] = event.get("actor_role", record["last_change"].get("actor_role", ""))
    metadata, _body, _has = _frontmatter(path.read_text(encoding="utf-8"))
    metadata["review_state"] = record
    metadata["revision"] = int(metadata.get("revision", 0)) + 1
    _update_metadata(metadata, record)
    body = _render_views(body, record)
    rendered = _dump_review(metadata, body)
    new_digest = _atomic_write(path, rendered, expected_digest)
    return {"ok": True, "changed": True, "revision": metadata["revision"], "record_digest": new_digest, **_derive(record)}


def _emit(payload: dict[str, Any], status: int = 0) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=True, indent=2)
    sys.stdout.write("\n")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("review")
    inspect_parser.add_argument("--pr-id", type=int)
    inspect_parser.add_argument("--json", action="store_true")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("review")
    apply_parser.add_argument("--event", required=True)
    apply_parser.add_argument("--expected-digest", required=True)
    apply_parser.add_argument("--repo-root", default=".")
    apply_parser.add_argument("--json", action="store_true")
    render_parser = sub.add_parser("render")
    render_parser.add_argument("review")
    render_parser.add_argument("--expected-digest", required=True)
    render_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        path = Path(args.review).resolve()
        if args.command == "inspect":
            return _emit(inspect(path, args.pr_id))
        if args.command == "apply":
            result = apply(path, Path(args.event).resolve(), args.expected_digest, Path(args.repo_root).resolve())
            return _emit(result)
        record, body, digest = _load(path)
        if digest != args.expected_digest:
            raise StateError("stale-record", "Review changed after it was inspected.", str(path))
        original = path.read_bytes()
        metadata, _body, _ = _frontmatter(original.decode("utf-8"))
        if "review_state" not in metadata:
            raise StateError("missing-modern-record", "Rendering requires a modern review_state record.", "review_state")
        rendered_body = _render_views(body, record)
        _update_metadata(metadata, record)
        data = _dump_review(metadata, rendered_body)
        if data == original:
            return _emit({"ok": True, "changed": False, "revision": metadata.get("revision"),
                          "record_digest": digest, **_derive(record)})
        metadata["revision"] = int(metadata.get("revision", 0)) + 1
        data = _dump_review(metadata, rendered_body)
        new_digest = _atomic_write(path, data, args.expected_digest)
        return _emit({"ok": True, "changed": new_digest != digest, "revision": metadata.get("revision"), "record_digest": new_digest, **_derive(record)})
    except StateError as exc:
        return _emit({"ok": False, "issues": [exc.issue]}, 1)
    except OSError as exc:
        return _emit({"ok": False, "issues": [{"code": "io-error", "message": "Review state operation failed.", "location": str(path), "recovery": str(exc)}]}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
