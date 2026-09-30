import json
from types import SimpleNamespace
import pytest
from scripts import dashboard_status as status


@pytest.mark.parametrize("api_state,expected", [("running", True), ("exited", False)])
def test_all_services_required(monkeypatch, api_state, expected):
    rows = [{"Service": name, "State": api_state if name == "api" else "running"}
            for name in ("r1", "r2", "api", "api-net", "client")]
    monkeypatch.setattr(status.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(rows)))
    assert status.lab_status()[0] is expected


def test_progress_prefers_latest_stage():
    assert status.current_stage("Starting common setup\nStarting section recovery\nRunning required Groq analysis") == "AI analysis and report"
