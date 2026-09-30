import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.run_project import run_pipeline


def test_missing_key_does_not_start_tests(tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Must not run")
    assert run_pipeline(tmp_path, {}, forbidden) == 2


def test_old_evidence_is_not_used(tmp_path):
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports/network-evidence.json").write_text('{"finished_at":"old"}')
    calls = []
    def runner(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1)
    assert run_pipeline(tmp_path, {"GROQ_API_KEY": "fake"}, runner) == 1
    assert len(calls) == 1


def test_failed_tests_still_analysed_but_not_successful(tmp_path):
    def runner(command, cwd, env):
        folder = Path(env["NETAPP_REPORT_DIR"])
        if command[1].endswith("network_suite.py"):
            (folder / "network-evidence.json").write_text('{"finished_at":"now"}')
            return SimpleNamespace(returncode=1)
        (folder / "ai-report.json").write_text('{"ai_analysis":{"status":"complete"}}')
        return SimpleNamespace(returncode=0)
    assert run_pipeline(tmp_path, {"GROQ_API_KEY": "fake"}, runner) == 1
    status = json.loads(next((tmp_path / "reports/runs").glob("*/pipeline-status.json")).read_text())
    assert status["ai"] == "complete"
    assert status["successful"] is False


@pytest.mark.parametrize("ai_status,exit_code", [("complete", 0), ("incomplete", 1)])
def test_pipeline_requires_ai_completion(tmp_path, ai_status, exit_code):
    def runner(command, cwd, env):
        folder = Path(env["NETAPP_REPORT_DIR"])
        if command[1].endswith("network_suite.py"):
            (folder / "network-evidence.json").write_text('{"finished_at":"now"}')
            return SimpleNamespace(returncode=0)
        (folder / "ai-report.json").write_text(json.dumps({"ai_analysis": {"status": ai_status}}))
        return SimpleNamespace(returncode=exit_code)
    assert run_pipeline(tmp_path, {"GROQ_API_KEY": "fake"}, runner) == exit_code
