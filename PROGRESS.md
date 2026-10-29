# PROGRESS

## Phase 0 — scaffold + data + profiling (Day 1)

### Done
- Repo scaffold (§5 layout), `pyproject.toml` (entry point `rockwatch`), `requirements.txt`, `.gitignore`, `.env.example`.
- `config/default.yaml`: inventory cleaning tables, profiling params, weather/quake/llm stubs.
- `rockwatch/data/usgs_inventory.py`: ScienceBase fetch (raises, never fabricates), CSV/zip load, cleaning (§6.1).
- `rockwatch/data/profiling.py`: counts, positive zone-days, sliding-window region ranking, chronological split proposal w/ 30-d gaps.
- `rockwatch/data/yosemite.py`: optional DS746 fetch/load.
- `rockwatch/cli.py`: `fetch-inventory`, `profile`; other §15 commands stubbed (exit 3).
- Tests: 13 passing (cleaning, zip load, region ranking, splits, CLI) on synthetic test-only frames.

### Pending / BLOCKED
- **BLOCKED: inventory download.** Agent sandboxes (cloud + local VM) get HTTP 403 from egress proxy for
  sciencebase.gov, archive-api.open-meteo.com, earthquake.usgs.gov, pubs.usgs.gov.
  Fix A: user places `US_Landslide_v3_csv` (zip or csv) in `data/raw/usgs_ls_v3/`.
  Fix B: allow those domains in Claude network settings (needed anyway for Phase 1 weather/quake fetch).
  Fix C: user runs `python -m rockwatch fetch-inventory` natively on Windows (normal internet).
- `docs/data_profile.md` NOT generated yet (no real data; nothing fabricated).
- CLAUDE.md: copy master prompt into repo root.
- CP1 not reached.

### Deviations
- See DECISIONS.md D-001..D-006.
