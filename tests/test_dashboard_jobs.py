from unittest.mock import Mock
import pytest
from scripts import dashboard_jobs as jobs


def test_active_job_blocks_duplicate(monkeypatch):
    manager = jobs.JobManager()
    manager.process = Mock()
    manager.process.poll.return_value = None
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: pytest.fail("Duplicate launch"))
    with pytest.raises(RuntimeError, match="already active"):
        manager.start()


def test_missing_key_blocks_launch(monkeypatch):
    manager = jobs.JobManager()
    monkeypatch.setattr(jobs, "pipeline_busy", lambda: False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        manager.start()


def test_launch_does_not_put_key_in_command(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "pipeline_busy", lambda: False)
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    launch = Mock()
    monkeypatch.setattr(jobs.subprocess, "Popen", launch)
    jobs.JobManager().start()
    args, kwargs = launch.call_args
    assert "test-secret" not in repr(args)
    assert kwargs["env"]["GROQ_API_KEY"] == "test-secret"
    assert kwargs["start_new_session"] is True
