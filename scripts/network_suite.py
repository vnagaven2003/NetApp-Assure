"""pyATS checks for the dedicated local Docker lab only."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from pyats import aetest

from check_lab import ROOT, check, check_network, execute
from lab_config import current_config

CONFIG = current_config()

EVIDENCE = {"started_at": datetime.now(timezone.utc).isoformat(),
            "scenario": CONFIG.scenario, "configuration": CONFIG.model_dump(mode="json"),
            "ai_analysis": {"status": "not_implemented"}, "workflow_complete": False}
RESTORE_REQUIRED = False
API_RESTORE_REQUIRED = False


def api_action(action):
    if action not in ("stop", "start"):
        raise ValueError("Unsupported API action")
    subprocess.run(["docker", "compose", "-f", "compose.lab.yaml", action, "api"],
                   cwd=ROOT, check=True, timeout=30)


def observe_http():
    output = execute("client", "python", "-c",
        "import json,urllib.request,urllib.error,sys; "
        "\ntry:\n r=urllib.request.urlopen(sys.argv[1],timeout=int(sys.argv[2])); print(json.dumps({'reachable':True,'status':r.status}))"
        "\nexcept urllib.error.HTTPError as e: print(json.dumps({'reachable':True,'status':e.code}))"
        "\nexcept (urllib.error.URLError,TimeoutError,OSError) as e: print(json.dumps({'reachable':False,'error':str(e)}))", CONFIG.application.url, str(CONFIG.timeouts.request_seconds))
    return json.loads(output)


def wait_healthy(seconds=None):
    seconds = CONFIG.timeouts.recovery_seconds if seconds is None else seconds
    deadline = time.monotonic() + seconds
    while True:
        try:
            result = check()
            if time.monotonic() > deadline:
                raise TimeoutError("Healthy state reached after recovery deadline")
            return result
        except (RuntimeError, subprocess.SubprocessError, ValueError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)


class Baseline(aetest.CommonSetup):
    @aetest.subsection
    def healthy_lab(self):
        EVIDENCE["baseline"] = wait_healthy()
        state = json.loads(execute("r1", "ip", "-j", "link", "show", "eth1"))[0]
        if "UP" not in state["flags"]:
            self.failed("Fault target must initially be administratively up")
        EVIDENCE["original_interface"] = state


class LinkFailure(aetest.Testcase):
    @aetest.test
    def interruption(self):
        global RESTORE_REQUIRED
        # Set before mutation: even a command timeout may have changed the link.
        RESTORE_REQUIRED = True
        try:
            execute("r1", "ip", "link", "set", "eth1", "down")
            state = json.loads(execute("r1", "ip", "-j", "link", "show", "eth1"))[0]
            EVIDENCE["fault_interface"] = state
            if "UP" in state["flags"]:
                self.failed("Interface did not go administratively down")
            # Docker exec errors are NOT accepted as network failure evidence.
            try:
                observation = observe_http()
                EVIDENCE["fault_request"] = observation
                if observation["reachable"]:
                    self.failed("Application remained reachable with the transit link down")
            finally:
                EVIDENCE["fault_neighbors"] = json.loads(execute("r1", "vtysh", "-c", "show ip ospf neighbor json"))
        finally:
            execute("r1", "ip", "link", "set", "eth1", "up")
            RESTORE_REQUIRED = False
            EVIDENCE["restore_command"] = "succeeded"

    @aetest.test
    def recovery(self):
        started = time.monotonic()
        EVIDENCE["recovery"] = wait_healthy()
        EVIDENCE["recovery_check_seconds"] = round(time.monotonic() - started, 3)


class ApplicationFailure(aetest.Testcase):
    @aetest.setup
    def healthy_before_fault(self):
        EVIDENCE["application_scenario"] = {"baseline": wait_healthy()}

    @aetest.test
    def stopped_application(self):
        global API_RESTORE_REQUIRED
        scenario = EVIDENCE["application_scenario"]
        API_RESTORE_REQUIRED = True
        try:
            api_action("stop")
            state = subprocess.check_output(
                ["docker", "compose", "-f", "compose.lab.yaml", "ps", "--all", "--format", "json", "api"],
                cwd=ROOT, text=True, timeout=15)
            # Compose emits one JSON object per line; tolerate array form too.
            rows = json.loads(state) if state.lstrip().startswith("[") else [json.loads(line) for line in state.splitlines() if line.strip()]
            scenario["container_state"] = rows
            if len(rows) != 1 or rows[0].get("State") != "exited":
                self.failed("API container stop was not verified")
            scenario["network_during_fault"] = check_network()
            scenario["http_during_fault"] = observe_http()
            if scenario["http_during_fault"]["reachable"]:
                self.failed("HTTP remained reachable while the API container was stopped")
        finally:
            api_action("start")
            API_RESTORE_REQUIRED = False
            scenario["restart_command"] = "succeeded"

    @aetest.test
    def application_recovery(self):
        EVIDENCE["application_scenario"]["recovery"] = wait_healthy()


class Cleanup(aetest.CommonCleanup):
    @aetest.subsection
    def restore_and_save(self):
        try:
            errors = []
            for required, restore in (
                (RESTORE_REQUIRED, lambda: execute("r1", "ip", "link", "set", "eth1", "up")),
                (API_RESTORE_REQUIRED, lambda: api_action("start")),
            ):
                if required:
                    try:
                        restore()
                    except Exception as error:
                        errors.append(str(error))
            if errors:
                raise RuntimeError("; ".join(errors))
            if "original_interface" in EVIDENCE:
                EVIDENCE["final_health"] = wait_healthy()
        except Exception as error:
            EVIDENCE["cleanup_error"] = str(error)
            raise
        finally:
            EVIDENCE["finished_at"] = datetime.now(timezone.utc).isoformat()
            EVIDENCE["pyats_result_before_cleanup_completion"] = str(self.parent.result)
            directory = Path(os.environ.get("NETAPP_REPORT_DIR", str(ROOT / "reports")))
            directory.mkdir(exist_ok=True)
            (directory / "network-evidence.json").write_text(json.dumps(EVIDENCE, indent=2))


if __name__ == "__main__":
    if CONFIG.scenario not in ("all", "link"):
        aetest.skip.affix(LinkFailure, reason="Not selected in this run")
    if CONFIG.scenario not in ("all", "application"):
        aetest.skip.affix(ApplicationFailure, reason="Not selected in this run")
    aetest.main()
