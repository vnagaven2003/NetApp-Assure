from pathlib import Path
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def test_dashboard_loads_without_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("scripts.dashboard_status.lab_status", lambda: (True, {}))
    monkeypatch.setattr("scripts.dashboard_jobs.pipeline_busy", lambda: False)
    page = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard.py"))
    page.run(timeout=60)
    assert not page.exception
    if page.tabs:
        assert len(page.tabs) == 3
        assert page.tabs[0].markdown
        assert page.tabs[1].markdown
        assert page.tabs[2].json
    button = next(b for b in page.button if b.label == "Run tests and AI analysis")
    assert button.disabled
    selector = next(s for s in page.selectbox if s.label == "Scenario")
    assert selector.options == ["all", "baseline", "link", "application"]
    selector.select("baseline").run(timeout=60)
    assert not page.exception
