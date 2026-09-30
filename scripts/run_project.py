"""Run the real lab scenarios and required AI stage in an isolated report directory."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(root, env, runner=subprocess.run, config_path=None, scenario=None):
    from scripts.lab_config import DEFAULT_CONFIG, load_config
    import yaml
    try:
        config = load_config(config_path or DEFAULT_CONFIG, scenario)
    except ValueError as error:
        print(f"Invalid lab configuration: {error}")
        return 2
    if not env.get("GROQ_API_KEY"):
        print("Set and export GROQ_API_KEY in this terminal before starting. No tests were run.")
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = root / "reports" / "runs" / run_id
    directory.mkdir(parents=True)
    snapshot = directory / "configuration.yaml"
    snapshot.write_text(yaml.safe_dump(config.model_dump(mode="json")), encoding="utf-8")
    child_env = dict(env, NETAPP_REPORT_DIR=str(directory), NETAPP_CONFIG=str(snapshot), NETAPP_SCENARIO=config.scenario)
    status = {"run_id": run_id, "tests": "not_started", "ai": "not_started", "workflow_complete": False}
    status["scenario"] = config.scenario
    try:
        print(f"Reports: {directory}\nRunning pyATS scenarios…", flush=True)
        tests = runner([sys.executable, str(root / "scripts/network_suite.py")], cwd=root, env=child_env)
        status["test_exit_code"] = tests.returncode
        status["tests"] = "passed" if tests.returncode == 0 else "failed_or_errored"
        evidence_file = directory / "network-evidence.json"
        if not evidence_file.is_file():
            status["error"] = "Test process produced no evidence for this run. AI was not called."
            return 1
        evidence = json.loads(evidence_file.read_text())
        if not evidence.get("finished_at"):
            status["error"] = "Test evidence is unfinished. AI was not called."
            return 1
        print("Running required Groq analysis…", flush=True)
        ai = runner([sys.executable, str(root / "scripts/ai_report.py")], cwd=root, env=child_env)
        status["ai_exit_code"] = ai.returncode
        report_file = directory / "ai-report.json"
        report = json.loads(report_file.read_text()) if report_file.exists() else {}
        complete = ai.returncode == 0 and report.get("ai_analysis", {}).get("status") == "complete"
        status["ai"] = "complete" if complete else "incomplete"
        status["workflow_complete"] = complete
        status["successful"] = tests.returncode == 0 and complete and not evidence.get("cleanup_error")
        if report:
            from scripts.report_view import render
            report["pipeline"] = status.copy()
            report["workflow_complete"] = complete
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            (directory / "report.html").write_text(render(report), encoding="utf-8")
        print(f"Tests: {status['tests']}; AI: {status['ai']}", flush=True)
        return 0 if status["successful"] else 1
    except KeyboardInterrupt:
        status["error"] = "Interrupted. Verify lab interface and API restoration before running again."
        return 130
    except (OSError, ValueError) as error:
        status["error"] = "A process or report file could not be handled. Check the console and lab state."
        return 1
    finally:
        (directory / "pipeline-status.json").write_text(json.dumps(status, indent=2))
        print(f"Run status saved: {directory / 'pipeline-status.json'}", flush=True)
        if "error" in status:
            print(status["error"])


def main():
    import argparse
    from scripts.lab_config import DEFAULT_CONFIG, SCENARIOS, load_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--validate-config", action="store_true")
    args = parser.parse_args()
    if args.validate_config:
        try:
            config = load_config(args.config, args.scenario)
        except ValueError as error:
            print(f"Invalid lab configuration: {error}")
            return 2
        print(f"Configuration valid. Scenario: {config.scenario}")
        return 0
    # The lab is shared; serialize runs launched through this command.
    import fcntl
    (ROOT / "reports").mkdir(exist_ok=True)
    with (ROOT / "reports/pipeline.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another project run is using the lab. Wait for it to finish.")
            return 2
        return run_pipeline(ROOT, os.environ, config_path=args.config, scenario=args.scenario)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
