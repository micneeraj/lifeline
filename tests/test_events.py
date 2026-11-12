"""Event-agnostic pipeline: the whole pipeline runs from an event manifest.

Uses a tiny synthetic test event (tests/fixtures/test-event: one small square flood polygon, a made-up town,
two fake charities). It is test-only and never loaded or shown by the app.
"""
import importlib.util, json, re, shutil
from pathlib import Path

import pytest

from lifeline import agents, config, paypal, pipeline

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "test-event"
APPEALS = {a["id"]: a for a in json.loads((ROOT / "eval/appeals.json").read_text(encoding="utf-8"))}
PUBLISHED = {r["id"]: r for r in json.loads((ROOT / "eval/results_v1.json").read_text(encoding="utf-8"))["rows"]}


def _build_data():
    spec = importlib.util.spec_from_file_location("build_data", ROOT / "scripts" / "build_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def test_event(tmp_path):
    ev = tmp_path / "test-event"
    shutil.copytree(FIXTURE, ev, ignore=shutil.ignore_patterns("test.db", "flood.geojson"))
    _build_data().main(str(ev / "event.json"))          # same builder as the real event, paths from the manifest
    agents.use_event(ev / "event.json")
    try:
        yield ev
    finally:
        agents.use_event(config.DEFAULT_EVENT)


def run(text, posted=None):
    return pipeline.run_check(text, posted, explain=False)


def test_helene_manifest_reproduces_locked_event_config():
    m = config.load_manifest(config.DEFAULT_EVENT)
    assert m["id"] == "helene-nc-2024" and m["state"] == "NC" and m["fema_decl"] == "DR-4827-NC"
    assert config.EVENT == {"name": "Hurricane / Tropical Storm Helene (DR-4827-NC)", "fema_decl": "DR-4827-NC",
                            "begin": "2024-09-25", "end": "2024-12-18", "obs_begin": "2024-09-24",
                            "obs_end": "2024-10-05"}
    fema = json.loads((ROOT / m["fema_file"]).read_text(encoding="utf-8"))["DisasterDeclarationsSummaries"]
    assert sorted(m["declared_counties"]) == sorted({d["designatedArea"].replace(" (County)", "") for d in fema})


def test_manifest_missing_keys_is_rejected(tmp_path):
    p = tmp_path / "event.json"
    p.write_text(json.dumps({"id": "x", "name": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        config.load_manifest(p)


def test_whole_pipeline_runs_from_a_synthetic_manifest(test_event):
    assert config.EVENT_MANIFEST["id"] == "test-event" and config.DB_PATH == (test_event / "test.db").resolve()
    r = run("Floodburg, Vermont flooded on 3 May 2030. Families need water and blankets.")
    assert r["verdict"] == "GREEN", r["reasons"]
    assert r["location"]["place"] == "Floodburg" and r["location"]["county"] == "Testcounty"
    assert r["flood"]["fema"] == "YES" and r["flood"]["flood"] == "IN_FLOOD"
    assert r["flood"]["flood_row"]["product"] == "Synthetic test flood polygon"
    assert {c["ein"] for c in r["charities"]} == {"990000001", "990000002"}
    assert all(c["county"] == "Testcounty" and c["county_declared"] for c in r["charities"])
    assert r["flood_evidence"]["band"] == "Strong"
    assert r["inputs_sha256"] and r["event"]["id"] == "test-event"
    # the receipt pays only the fake registered charities, never the person who posted
    rc = paypal.settle(r, paypal.authorize(paypal.create_order(20, r["check_id"])["id"], r["check_id"]), 20)
    assert rc["action"] == "CAPTURED_AND_PAID" and not rc["poster_paid"]
    assert {p["ein"] for p in rc["payouts"]} == {"990000001", "990000002"}


def test_synthetic_event_rules_come_from_the_manifest(test_event):
    dry = run("Drytown, Vermont flooded on 3 May 2030. Please send money.")
    assert dry["verdict"] == "RED"
    assert "NO_DISASTER_DECLARATION" in dry["reasons"] and "NOT_IN_FLOOD_AREA" in dry["reasons"]
    assert any("DR-9999-VT" in t for t in dry["reason_text"])
    late = run("Floodburg, Vermont flooded on 3 Sep 2030. Families need water.")
    assert late["verdict"] == "RED" and "DATE_MISMATCH" in late["reasons"]
    assert any("Synthetic Test Flood" in t for t in late["reason_text"])
    other_state = run("Floodburg, Ohio flooded on 3 May 2030. Families need water.")
    assert other_state["verdict"] != "GREEN"


def test_switching_back_restores_helene_hashes(test_event):
    agents.use_event(config.DEFAULT_EVENT)
    a = APPEALS["in-02"]
    r = pipeline.run_check(a["text"], a["posted_at"], appeal_id="in-02", explain=False)
    assert r["verdict_sha256"] == PUBLISHED["in-02"]["lifeline"]["verdict_sha256"]


def test_no_hard_coded_event_in_rules_or_ui():
    for f in ("lifeline/agents.py", "lifeline/pipeline.py", "app/main.py", "static/index.html", "static/review.html"):
        src = (ROOT / f).read_text(encoding="utf-8")
        assert "DR-4827" not in src, f
        assert not re.search(r"[!=]=\s*\"NC\"", src), f
        assert "Helene" not in src, f
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    assert "North Carolina" not in html and "western NC" not in html
    cfg = (ROOT / "lifeline/config.py").read_text(encoding="utf-8")
    assert "2024-09-25" not in cfg and "WNC_BBOX" not in cfg


def test_add_an_event_doc_exists():
    doc = (ROOT / "docs/ADD_AN_EVENT.md").read_text(encoding="utf-8")
    for k in ("event.json", "declared_counties", "fema_decl", "build_data.py", "LIFELINE_EVENT"):
        assert k in doc
