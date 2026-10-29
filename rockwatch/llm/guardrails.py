"""Guardrails enforced in code (§9.4). The model is never trusted to follow them."""
from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_ACTIONS = {
    1: ["Increase monitoring of slopes in the zone."],
    2: ["Increase monitoring of slopes in the zone.", "Restrict access below slopes in the zone."],
    3: ["Increase monitoring of slopes in the zone.", "Restrict access below slopes in the zone.", "Close or evacuate the zone."],
}
DECISIONS = {"CONFIRM", "DOWNGRADE", "HOLD"}
NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
TIME_OF_FAILURE = re.compile(r"(when|what time|which day|exact(ly)?\s+(time|date|day)).{0,40}(fail|collapse|slide|rockfall|happen)", re.I)
FIELD_PERF = re.compile(r"(field|mine|real[- ]world|production)\s+(performance|accuracy|validated|validation)|how accurate .* (mine|field)", re.I)


def parse_json(text: str) -> dict[str, Any] | None:
    """First JSON object in text (models sometimes wrap it)."""
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            v = json.loads(m.group(0))
            return v if isinstance(v, dict) else None
        except ValueError:
            return None
    return None


def flatten_numbers(obj: Any, out: list[float] | None = None) -> list[float]:
    out = [] if out is None else out
    if isinstance(obj, bool):
        out.append(float(obj))
    elif isinstance(obj, (int, float)):
        if obj == obj:
            out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            flatten_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            flatten_numbers(v, out)
    elif isinstance(obj, str):
        out += [float(x) for x in NUM.findall(obj)]
    return out


def flatten_strings(obj: Any, out: set[str] | None = None) -> set[str]:
    out = set() if out is None else out
    if isinstance(obj, str):
        out.add(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            flatten_strings(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            flatten_strings(v, out)
    return out


def numbers_ok(text: str, evidence: Any, tol: float = 0.01) -> tuple[bool, list[str]]:
    """Every number in text must match an evidence value (rel. tol 1%, or equal to it rounded to the shown decimals).
    Identifier/date strings that appear verbatim in the evidence and level tokens L0–L3 are not numbers."""
    t = text or ""
    for s in sorted((x for x in flatten_strings(evidence) if any(ch.isdigit() for ch in x) and len(x) >= 3), key=len, reverse=True):
        t = t.replace(s, " ")
    t = re.sub(r"\bL[0-3]\b", " ", t)
    vals = flatten_numbers(evidence)
    bad = []
    for tok in NUM.findall(t):
        x = float(tok)
        nd = len(tok.split(".")[1]) if "." in tok else 0
        if not any(abs(x - v) <= tol * max(abs(v), 1e-12) or round(v, nd) == x for v in vals):
            bad.append(tok)
    return (not bad), bad


def check_verifier(out: dict[str, Any] | None, current: int, quality: dict[str, str], contributions: dict[str, float],
                   evidence: Any, evidence_ids: set[str]) -> list[str]:
    """Return violations (empty = pass)."""
    if out is None:
        return ["invalid_json"]
    v = []
    for k in ("decision", "proposed_level", "confidence", "rationale", "evidence_ids", "missing_evidence"):
        if k not in out:
            v.append(f"missing_field:{k}")
    if v:
        return v
    d, lvl = out["decision"], out["proposed_level"]
    if d not in DECISIONS:
        v.append("bad_decision")
    if not isinstance(lvl, int) or lvl not in (current, current - 1):
        v.append("level_not_current_or_minus_one")
    if d in ("CONFIRM", "HOLD") and lvl != current:
        v.append("decision_level_mismatch")
    if d == "DOWNGRADE":
        if lvl != current - 1:
            v.append("decision_level_mismatch")
        if current >= 3:
            v.append("downgrade_forbidden_L3")
        if any(q != "ok" for q in quality.values()):
            v.append("downgrade_forbidden_quality")
        if contributions.get("seismic", 0.0) > 0:
            v.append("downgrade_forbidden_seismic")
    if not isinstance(out["confidence"], (int, float)) or not 0 <= out["confidence"] <= 1:
        v.append("bad_confidence")
    if len(str(out["rationale"]).split()) > 60:
        v.append("rationale_too_long")
    ok, bad = numbers_ok(str(out["rationale"]), evidence)
    if not ok:
        v.append(f"unsupported_numbers:{bad}")
    if not isinstance(out["evidence_ids"], list) or any(e not in evidence_ids for e in out["evidence_ids"]):
        v.append("unknown_evidence_id")
    return v


def check_composer(out: dict[str, Any] | None, level: int, alert: Any) -> list[str]:
    if out is None:
        return ["invalid_json"]
    v = [f"missing_field:{k}" for k in ("headline", "body", "actions") if k not in out]
    if v:
        return v
    if len(str(out["body"]).split()) > 80:
        v.append("body_too_long")
    allowed = ALLOWED_ACTIONS.get(level, [])
    if not isinstance(out["actions"], list) or any(a not in allowed for a in out["actions"]):
        v.append("action_not_allowed")
    for f in ("headline", "body"):
        ok, bad = numbers_ok(str(out[f]), alert)
        if not ok:
            v.append(f"unsupported_numbers:{f}:{bad}")
    if TIME_OF_FAILURE.search(str(out["body"])):
        v.append("time_of_failure_claim")
    return v


def template_message(alert: dict[str, Any]) -> dict[str, Any]:
    """Deterministic fallback composer."""
    lvl = alert["level"]
    name = {1: "Watch", 2: "Warning", 3: "Alarm"}.get(lvl, "Normal")
    return {"headline": f"L{lvl} {name} — zone {alert['zone_id']} ({alert['date']})",
            "body": f"Daily landslide-risk estimate p={alert['p']:.3f}; main contribution: {alert['top_modality']}. "
                    "This is a daily probability, not a failure time.",
            "actions": ALLOWED_ACTIONS.get(lvl, []), "source": "template"}


def analyst_refusal(question: str) -> str | None:
    if TIME_OF_FAILURE.search(question):
        return "RockWatch cannot predict when a slope will fail; it estimates daily risk with lead time in days."
    if FIELD_PERF.search(question):
        return "RockWatch has no field or mine validation; reported metrics are on historical US inventory data only (precision is a lower bound)."
    return None


def check_analyst(out: dict[str, Any] | None, records: list[dict[str, Any]]) -> list[str]:
    if out is None:
        return ["invalid_json"]
    if "answer" not in out or "citations" not in out:
        return ["missing_field"]
    ids = {str(r["id"]) for r in records}
    v = []
    cited = set(re.findall(r"\[([^\]]+)\]", str(out["answer"]))) | {str(c) for c in out["citations"]}
    if any(c not in ids for c in cited):
        v.append("unknown_citation")
    if records and not cited and "no logged records" not in str(out["answer"]).lower():
        v.append("no_citation")
    ok, bad = numbers_ok(str(out["answer"]), records)
    if not ok:
        v.append(f"unsupported_numbers:{bad}")
    if TIME_OF_FAILURE.search(str(out["answer"])):
        v.append("time_of_failure_claim")
    return v
