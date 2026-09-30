"""Read-only lab readiness and progress helpers."""
import json
import subprocess
from scripts.dashboard_jobs import ROOT


def lab_status():
    try:
        result = subprocess.run(["docker", "compose", "-f", "compose.lab.yaml", "ps", "--all", "--format", "json"], cwd=ROOT, capture_output=True, text=True, timeout=5, check=True)
        raw = result.stdout.strip()
        rows = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines() if line.strip()]
        services = {r["Service"]: r.get("State", "unknown") for r in rows}
        return all(services.get(n) == "running" for n in ("r1", "r2", "api", "api-net", "client")), services
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return False, {}


def current_stage(log):
    for marker, label in [("Running required Groq analysis", "AI analysis and report"), ("Starting common cleanup", "Final health and cleanup"), ("Starting section application_recovery", "Application recovery"), ("Starting section stopped_application", "Application interruption"), ("Starting testcase ApplicationFailure", "Application baseline"), ("Starting section recovery", "Network recovery: waiting for OSPF"), ("Starting section interruption", "Link interruption"), ("Starting common setup", "Healthy baseline")]:
        if marker in log:
            return label
    return "Starting test runner"
