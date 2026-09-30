"""Check OSPF, installed routes, and the actual HTTP path in the Docker lab."""

import json
from pathlib import Path
import subprocess
import time
try:
    from .lab_config import current_config
except ImportError:
    from lab_config import current_config

ROOT = Path(__file__).resolve().parents[1]


def execute(service, *args):
    return subprocess.check_output(
        ["docker", "compose", "-f", "compose.lab.yaml", "exec", "-T", service, *args],
        cwd=ROOT, text=True, timeout=15,
    )


def check_network():
    config = current_config()
    evidence = {}
    for router, expected in config.routers.items():
        peer, prefix = str(expected.peer), str(expected.remote_route)
        if execute(router, "ip", "route", "show", "default").strip():
            raise RuntimeError(f"{router}: unexpected default route could bypass OSPF")
        neighbors = json.loads(execute(router, "vtysh", "-c", "show ip ospf neighbor json"))
        if not any(n.get("nbrState", "").startswith("Full/") for n in neighbors.get("neighbors", {}).get(peer, [])):
            raise RuntimeError(f"{router}: expected Full OSPF neighbour {peer}: {neighbors}")
        routes = json.loads(execute(router, "vtysh", "-c", "show ip route json"))
        if not any(r.get("protocol") == "ospf" and r.get("installed") for r in routes.get(prefix, [])):
            raise RuntimeError(f"{router}: OSPF route not installed for {prefix}")
        evidence[router] = {"neighbors": neighbors, "route": routes[prefix]}
    trace = execute("client", "traceroute", "-n", "-I", "-q", "1", "-w", "1", "-m", "5", str(config.application.host))
    hops = [line.split()[1] for line in trace.splitlines()[1:] if len(line.split()) >= 2]
    if hops != [str(hop) for hop in config.expected_hops]:
        raise RuntimeError(f"Unexpected routed path: {trace}")
    evidence["traceroute"] = trace
    return evidence


def check():
    config = current_config()
    evidence = check_network()
    output = execute("client", "curl", "--silent", "--show-error", "--max-time", str(config.timeouts.request_seconds), "--write-out", "\n%{http_code}", config.application.url)
    raw, status = output.rsplit("\n", 1)
    body = json.loads(raw)
    if int(status) != config.application.expected_status or body != config.application.expected_json:
        raise RuntimeError(f"Unexpected API response: {body}")
    evidence["health"] = body
    evidence["application_check"] = {"matched": True, "status": int(status), "url": config.application.url}
    return evidence


if __name__ == "__main__":
    deadline = time.monotonic() + current_config().timeouts.recovery_seconds
    while True:
        try:
            result = check()
            break
        except (RuntimeError, subprocess.SubprocessError, ValueError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "lab-baseline.json").write_text(json.dumps(result, indent=2))
    print(result["traceroute"])
    print("PASS: both OSPF neighbours, installed remote routes, routed path, and API health.")
    print("Evidence saved to reports/lab-baseline.json (AI analysis not implemented yet).")
