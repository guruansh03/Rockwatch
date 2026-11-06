"""Control-room web API: every GET route on a recorded run, POST actions, static files, and the HTTP layer."""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from rockwatch.config import load_config, repo_path

RUNS = sorted((p for p in repo_path("data/runs").glob("*") if (p / "bus.sqlite").exists() and (p / "run.json").exists()),
              key=lambda p: (p / "run.json").stat().st_mtime)
pytestmark = pytest.mark.skipif(not RUNS, reason="no recorded run")


@pytest.fixture(scope="module")
def app():
    from rockwatch.dashboard.server import App
    return App(load_config())


@pytest.fixture(scope="module")
def run():
    return RUNS[-1].name


def test_get_routes(app, run):
    assert any(r["name"] == run for r in app.api_runs({}))
    m = app.api_meta({"run": run})
    assert m["zones"] and m["days_total"] > 0 and "not mine performance" in m["banner"]
    s = app.api_state({"run": run})
    assert s["status"] in ("live", "paused", "finished", "starting") and isinstance(s["levels"], dict)
    assert app.api_history({"run": run})
    z = app.api_zone({"run": run, "zone": m["zones"][0]["zone_id"]})
    assert z["series"] and set(z["evidence"]) >= {"rain", "susceptibility"}
    assert isinstance(app.api_alerts({"run": run}), list)
    ag = app.api_agents({"run": run})
    assert ag["agents"] and {"agent", "pid", "supervisor"} <= set(ag["agents"][0])
    assert isinstance(app.api_truth({"run": run}), list)
    h = app.api_history({"run": run})
    assert {"l0", "l1", "l2", "l3", "n", "max", "truth"} <= set(h[0])
    # day inspection: state as of an earlier closed day, truth never beyond that day
    d0 = h[0]["day"]
    s0 = app.api_state({"run": run, "day": d0})
    assert s0["day"] == d0 and s0["view"] == d0 and s0["latest_day"] == h[-1]["day"]
    assert all(t["date"] <= d0 for t in app.api_truth({"run": run, "day": d0, "days": 400}))
    assert "key" not in json.dumps(m["llm_setup"]).lower() or m["llm_setup"].get("key_set") in (True, False)
    reps = app.api_reports({})
    if reps:
        r = app.api_report({"name": reps[0]["name"]})
        assert "rockwatch" in r["metrics"]


def test_unknown_run_is_404(app):
    with pytest.raises(FileNotFoundError):
        app.run_dir("does-not-exist")


def test_post_validation(app, run):
    assert app.post_control({"run": run, "kind": "rm -rf"})["ok"] is False
    assert app.post_control({"run": run, "kind": "speed", "payload": {"s": 0.1}})["ok"] is False
    assert app.post_control({"run": run, "kind": "speed", "payload": {"s": "fast"}})["ok"] is False
    assert app.post_agent({"run": run, "agent": "nope", "action": "kill"})["ok"] is False
    a = app.post_ask({"run": run, "question": "When exactly will the slope fail?"})
    assert a["source"] == "refusal"
    a = app.post_ask({"run": run, "question": "Which alerts were raised?"})
    assert a["source"] in ("records", "template") and a["answer"]


def test_http_layer(run):
    from rockwatch.dashboard.server import serve
    srv = serve(port=0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        html = opener.open(base + "/").read().decode()
        assert "RockWatch" in html and "/static/app.js" in html
        for path in ("/static/app.js", "/static/charts.js", "/static/app.css", "/static/vendor/leaflet/leaflet.js",
                     "/static/vendor/fonts/fonts.css"):
            assert opener.open(base + path).status == 200
        st = json.loads(opener.open(f"{base}/api/state?run={run}").read())
        assert "levels" in st
        with pytest.raises(urllib.error.HTTPError) as e:
            opener.open(base + "/static/../server.py")
        assert e.value.code == 404
        req = urllib.request.Request(base + "/api/control", data=json.dumps({"run": run, "kind": "bogus"}).encode(),
                                     headers={"Content-Type": "application/json"})
        assert json.loads(opener.open(req).read())["ok"] is False
    finally:
        srv.shutdown()
