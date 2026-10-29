# LLM agents and guardrails

All rules are enforced in code (`rockwatch/llm/guardrails.py`, `rockwatch/llm/runtime.py`); the model is never trusted to follow them.

## Agents
| Agent | Runs on | Inputs | Output |
|---|---|---|---|
| LLM-Verifier (`agents/llm_verifier.py`) | provisional L2+ zone-days only | 5 read-only tools: `get_zone_evidence`, `get_regional_extent`, `get_zone_history`, `get_data_quality`, `get_snow_context` (bus log live, feature panel in batch eval) | `{decision, proposed_level, confidence, rationale, evidence_ids, missing_evidence}` |
| LLM-AlertComposer (`agents/llm_composer.py`) | L2+ escalations | structured alert (level, p, contributions) | `{headline, body ≤80 words, actions}` |
| LLM-Analyst (`agents/llm_analyst.py`, `rockwatch ask`) | operator questions | `query_alerts`, `query_metrics`, `explain_zone` | `{answer, citations}` |

Providers: `anthropic` (Messages API + tool use, ≤4 tool turns), `ollama` (local; evidence pre-bundled), `mock` (deterministic rules; tests/CI).
Ground truth (`truth.events`) is unreadable by every LLM agent (bus access control + static test). Inventory `Notes` are never loaded.

## Verifier rules
- `proposed_level ∈ {current, current−1}`; the LLM can never raise a level.
- DOWNGRADE forbidden at L3, when any modality quality ≠ ok, or when the seismic contribution > 0.
- CONFIRM at L2 counts as L3 corroboration only if p ≥ t3 (code rule; the only path to a higher level).
- Every number in the rationale must match an evidence value (1% relative, or equal after rounding to the shown decimals); ids/dates copied from evidence are not numbers.
- Every `evidence_id` must exist in the evidence returned for that zone-day; rationale ≤ 60 words.
- Invalid JSON or any violation → one retry with the violations listed → deterministic level, `verifier=fallback`.

## Composer / Analyst rules
- Composer actions must be copied from the fixed per-level list (L1 monitor; L2 + restrict access below slopes; L3 + close/evacuate). Numbers validated; failure or LLM offline → fixed template.
- Analyst: refuses time-of-failure and field/mine-performance questions before calling any model; must cite record ids that exist in its tool results; numbers validated; failure → record list fallback.

## Operations
- Cache: `sha256(provider + model + system + user + evidence)` → `data/cache/llm/` (reruns reproducible, offline after first run).
- Sampling: Claude 5.5-family models reject `temperature`/`top_p` (400), so they are omitted (D-034); Ollama uses temperature 0; reproducibility comes from the cache.
- Timeout 20 s; `max_llm_calls` per eval run — batch eval verifies the highest-p candidates up to the cap, the rest keep the deterministic level and are counted (`FALLBACK_CAP`); live demo ≤ `llm_live.max_calls_per_day`.
- Usage (tokens, latency, cached, outcome, violations) → `llm.calls` topic live and `llm_usage.json` in eval reports. Cost is null unless prices are configured.
