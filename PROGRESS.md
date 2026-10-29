# PROGRESS

## Phase 0 — scaffold + data + profiling (Day 1) — DONE, waiting CP1

### Done
- Repo scaffold (§5), `pyproject.toml` (`rockwatch` entry point), requirements, `.gitignore`, `.env.example`.
- `config/default.yaml`: cleaning tables, profiling params, weather/quake/llm stubs.
- `data/usgs_inventory.py`: fetch (ScienceBase), point+poly CSV load, cleaning §6.1.
- `data/profiling.py`: counts, positive zone-days, sliding-bbox ranking (no-EQ), coverage-aware chronological splits w/ 30-d gaps.
- `data/yosemite.py`: DS746 fetch + parse.
- CLI: `fetch-inventory`, `profile` working; rest stubbed.
- Data: USGS v3 zip + DS746 xlsx in `data/raw/` (user-downloaded). `docs/data_profile.md` generated from real data.
- Tests: 15 passing.

### Pending
- **CP1**: confirm region, C_min, type mapping, split dates, Yosemite track.
- CLAUDE.md copy into repo root (not present yet).
- Python on dev VM is 3.10 (pyproject says ≥3.11); code kept 3.10-compatible.

### Deviations
- See DECISIONS.md D-001..D-012.
