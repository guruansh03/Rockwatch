# RockWatch-FuseGuard (SIH25071)

Multi-agent landslide early-warning prototype (historical replay). Team: Rumita Mandal, Guruansh Singh.

> **US natural-slope data; not open-pit mine performance. Precision is a lower bound (unreported events). Lead time in days.**

## Setup (Windows / macOS / Linux)
```
python -m venv .venv
# Windows: .venv\Scripts\activate   macOS/Linux: source .venv/bin/activate
pip install -e ".[ui,llm,dev]"
python -m rockwatch fetch-inventory     # or place US_Landslide_v3_csv in data/raw/usgs_ls_v3/
python -m rockwatch profile             # -> docs/data_profile.md
pytest -q
```

Data: USGS *Landslide Inventories across the United States* v3.0, DOI 10.5066/P14AJF8I (CC0). Weather data by Open-Meteo.com (CC BY 4.0). Earthquakes: USGS ComCat.

Status: Phase 0 (see PROGRESS.md).
