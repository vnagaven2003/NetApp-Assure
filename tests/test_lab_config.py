import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.lab_config import DEFAULT_CONFIG, load_config
from scripts.run_project import run_pipeline
from scripts.report_view import render


@pytest.mark.parametrize("field,value", [("scenario", "unknown"), ("unexpected", True),
    ("timeouts", {"request_seconds": True, "recovery_seconds": 90}),
    ("routers", {})])
def test_invalid_config_rejected(tmp_path, field, value):
    data = yaml.safe_load(DEFAULT_CONFIG.read_text())
    data[field] = value
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_config(path)
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration must not launch processes")
    assert run_pipeline(tmp_path, {"GROQ_API_KEY": "fake"}, forbidden, config_path=path) == 2
    assert not (tmp_path / "reports").exists()


def test_selected_scenario_saved_and_forwarded(tmp_path):
    calls = []
    def runner(command, cwd, env):
        calls.append(command)
        assert env["NETAPP_SCENARIO"] == "baseline"
        assert load_config(env["NETAPP_CONFIG"]).scenario == "baseline"
        folder = Path(env["NETAPP_REPORT_DIR"])
        if command[1].endswith("network_suite.py"):
            (folder / "network-evidence.json").write_text(json.dumps({"finished_at": "now"}))
        else:
            (folder / "ai-report.json").write_text('{"ai_analysis":{"status":"complete"}}')
        return SimpleNamespace(returncode=0)
    assert run_pipeline(tmp_path, {"GROQ_API_KEY": "fake"}, runner, scenario="baseline") == 0
    assert len(calls) == 2


def test_baseline_report_marks_faults_not_selected():
    page = render({"measured_evidence": {"scenario": "baseline"}})
    assert page.count("<td>Not selected</td>") == 4
