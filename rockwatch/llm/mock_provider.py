"""Deterministic rule-based 'LLM' for tests/CI. Reads the structured bundle in `meta` (never free text).
`meta['_mock_fault']` makes it emit specific bad outputs so guardrails can be tested."""
from __future__ import annotations

import json

from rockwatch.llm.provider import LLMResult, Provider


class MockProvider(Provider):
    name = "mock"
    supports_tools = False

    def complete(self, system, user, tools=None, max_tokens=600, meta=None):
        meta = meta or {}
        task = meta.get("task")
        fault = meta.get("_mock_fault")
        if fault == "invalid_json":
            return LLMResult("not json {", self.name, self.model)
        out = {"verifier": self._verify, "composer": self._compose, "analyst": self._analyst}[task](meta)
        if fault == "raise_level":
            out["proposed_level"] = meta["current_level"] + 1
            out["decision"] = "CONFIRM"
        elif fault == "bad_number":
            out["rationale"] = "p is 0.987 which is very high."
        elif fault == "bad_evidence_id":
            out["evidence_ids"] = ["does-not-exist"]
        elif fault == "forbidden_downgrade":
            out.update(decision="DOWNGRADE", proposed_level=meta["current_level"] - 1)
        elif fault == "bad_action":
            out["actions"] = ["evacuate the entire state"]
        return LLMResult(json.dumps(out), self.name, self.model, input_tokens=len(user) // 4, output_tokens=60)

    @staticmethod
    def _verify(m):
        b = m["bundle"]
        cur = m["current_level"]
        c = b["contributions"]
        dyn_pos = [g for g in ("rain", "thermal", "seismic") if c.get(g, 0) > 0]
        ids = b["evidence_ids"][:3]
        if dyn_pos:
            g = max(dyn_pos, key=lambda k: c[k])
            return {"decision": "CONFIRM", "proposed_level": cur, "confidence": 0.7,
                    "rationale": f"Dynamic evidence supports the alert: {g} contribution {c[g]:.2f} with p {b['p']:.3f}.",
                    "evidence_ids": ids, "missing_evidence": []}
        if cur >= 2 and b["quality_ok"] and c.get("seismic", 0) <= 0 and cur < 3:
            return {"decision": "DOWNGRADE", "proposed_level": cur - 1, "confidence": 0.6,
                    "rationale": f"No dynamic modality is positive; static prior contribution {c.get('susceptibility', 0):.2f} drives p {b['p']:.3f}.",
                    "evidence_ids": ids, "missing_evidence": ["dynamic trigger"]}
        return {"decision": "HOLD", "proposed_level": cur, "confidence": 0.5,
                "rationale": f"Keeping level; p {b['p']:.3f}.", "evidence_ids": ids, "missing_evidence": []}

    @staticmethod
    def _compose(m):
        a = m["alert"]
        return {"headline": f"Level {a['level']} landslide-risk alert for zone {a['zone_id']}",
                "body": f"Estimated probability {a['p']:.3f} on {a['date']}. Largest contribution: {a['top_modality']}.",
                "actions": m["allowed_actions"][:2]}

    @staticmethod
    def _analyst(m):
        recs = m["records"][:3]
        if not recs:
            return {"answer": "No logged records match the question.", "citations": []}
        return {"answer": "Matching logged records: " + "; ".join(f"[{r['id']}]" for r in recs) + ".",
                "citations": [r["id"] for r in recs]}
