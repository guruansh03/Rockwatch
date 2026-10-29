"""Dashboard smoke test (Streamlit AppTest) against the latest recorded run; skipped if streamlit or runs are absent."""
import os

import pytest

from rockwatch.config import repo_path

st_testing = pytest.importorskip("streamlit.testing.v1")
RUNS = sorted(p for p in repo_path("data/runs").glob("*") if (p / "bus.sqlite").exists())


@pytest.mark.skipif(not RUNS, reason="no recorded run")
def test_dashboard_renders(monkeypatch):
    monkeypatch.setenv("ROCKWATCH_RUN_DIR", str(RUNS[-1]))
    monkeypatch.setenv("ROCKWATCH_AUTOREFRESH", "0")
    at = st_testing.AppTest.from_file(str(repo_path("rockwatch/dashboard/app.py")), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert any("RockWatch" in t.value for t in at.title)
    assert "not mine performance" in " ".join(m.value for m in at.markdown)


@pytest.mark.skipif(not RUNS, reason="no recorded run")
def test_dashboard_data_helpers():
    from rockwatch.bus.sqlite_bus import SqliteBus
    from rockwatch.dashboard import data as D
    b = SqliteBus(RUNS[-1] / "bus.sqlite")
    s = D.latest_state(b)
    assert s is not None and s.payload["levels"]
    assert not D.agent_table(b).empty
