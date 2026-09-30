"""Local background job launcher; contains no Streamlit dependencies."""
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]


def pipeline_busy():
    import fcntl
    (ROOT / "reports").mkdir(exist_ok=True)
    with (ROOT / "reports/pipeline.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False


class JobManager:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()

    def busy(self):
        return (self.process is not None and self.process.poll() is None) or pipeline_busy()

    def start(self, config_path=None, scenario=None):
        from scripts.lab_config import DEFAULT_CONFIG, load_config
        config_path = Path(config_path or DEFAULT_CONFIG).resolve()
        config = load_config(config_path, scenario)
        with self.lock:
            if self.busy():
                raise RuntimeError("A test run is already active.")
            if not os.environ.get("GROQ_API_KEY"):
                raise RuntimeError("Start Streamlit from the Ubuntu terminal where GROQ_API_KEY is exported.")
            directory = ROOT / "reports"
            directory.mkdir(exist_ok=True)
            with (directory / "dashboard-run.log").open("wb") as log:
                self.process = subprocess.Popen(
                    [sys.executable, "-u", str(ROOT / "scripts/run_project.py"),
                     "--config", str(config_path), "--scenario", config.scenario],
                    cwd=ROOT, env=os.environ.copy(), stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True,
                )

    def exit_code(self):
        return None if self.process is None else self.process.poll()
