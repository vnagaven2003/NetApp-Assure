"""Local Streamlit interface. Run in Ubuntu with the project environment active."""
import json
import os

import streamlit as st
from scripts.dashboard_status import lab_status, current_stage

from scripts.dashboard_jobs import ROOT, JobManager
from scripts.lab_config import DEFAULT_CONFIG, SCENARIOS, load_config

st.set_page_config(page_title="NetApp Assure", page_icon="🧪", layout="wide")


@st.cache_resource
def jobs():
    return JobManager()


@st.cache_data(ttl=10)
def readiness():
    return lab_status()


st.title("NetApp Assure")
with st.sidebar:
    st.header("Your testing workspace")
    st.write("**Local Docker lab**")
    st.caption("Python · pyATS · FRR · Groq")
    st.divider()
    st.write("**Scenarios**\n\n1. Network link interruption\n2. Application stop\n3. Recovery verification")
    st.caption("Choose which checks to run below. Closing the browser does not cancel a run.")
st.caption("Network and application testing · local Docker lab · AI-assisted explanations")
st.info("Fault scenarios deliberately interrupt the selected lab component, restore it, and verify recovery. Baseline checks introduce no faults.")
st.code("Test client → FRR Router 1 → FRR Router 2 → Python API", language=None)
st.subheader("Run the test suite")
st.write("Every run includes baseline checks, final health verification, and required Groq analysis.")
st.caption("Keep Docker and the lab running. Edit config/lab.yaml to change test expectations; it does not reconfigure the lab.")


@st.fragment(run_every="3s")
def controls():
    manager = jobs()
    active = manager.busy()
    try:
        settings = load_config(DEFAULT_CONFIG)
        valid_config = True
    except ValueError as error:
        settings = None
        valid_config = False
        st.error(f"Invalid config/lab.yaml: {error}")
    scenario = st.selectbox("Scenario", SCENARIOS,
        index=SCENARIOS.index(settings.scenario) if settings else 0, disabled=active)
    if settings:
        with st.expander("Validated test settings"):
            st.json(settings.model_dump(mode="json"))
    configured = bool(os.environ.get("GROQ_API_KEY"))
    ready, services = readiness()
    left, middle, right = st.columns(3)
    left.metric("Execution", "Running" if active else "Idle")
    middle.metric("Lab containers", "Running" if ready else "Check required")
    right.metric("AI credential", "Set (not yet validated)" if configured else "Missing")
    st.caption("Container status is checked every 10 seconds. Routing health is verified by the test baseline.")
    if not ready and not active:
        st.warning("Start Docker Desktop and all lab containers before running tests.")
        st.code("docker compose -f compose.lab.yaml up -d --wait", language="bash")
    with st.expander("Container status"):
        st.json(services or {"status": "Unavailable"})
    if not configured:
        st.warning("Export GROQ_API_KEY in Ubuntu, then start or restart Streamlit from that same terminal. No key is stored by this page.")
    if st.button("Run tests and AI analysis", type="primary", disabled=active or not configured or not ready or not valid_config):
        try:
            manager.start(config_path=DEFAULT_CONFIG, scenario=scenario)
            st.rerun(scope="fragment")
        except (OSError, RuntimeError, ValueError) as error:
            st.error(str(error))
    code = manager.exit_code()
    if not active and code is not None:
        if code == 0:
            st.success("Background run finished successfully. Open its report below.")
        else:
            st.error(f"Background run ended with exit code {code}. Review the log and run status; verify lab restoration if interrupted.")
    log = ROOT / "reports/dashboard-run.log"
    if log.exists():
        with log.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 24000))
            log_text = handle.read().decode("utf-8", errors="replace")
        if active:
            st.info(current_stage(log_text))
            st.caption("Updates every 3 seconds. OSPF recovery can take around a minute.")
        with st.expander("Execution log", expanded=False):
            with st.container(height=320):
                st.code(log_text, language=None)
    st.caption("Page refreshes do not launch tests. Closing the browser does not stop an active run. Do not run the standalone fault suite concurrently.")


controls()
st.divider()
st.subheader("Saved results")
st.button("Refresh report list")
folders = sorted((ROOT / "reports/runs").glob("*"), reverse=True)
choices = {p.name: p for p in folders if p.is_dir()}
if (ROOT / "reports/ai-report.json").exists():
    choices["Earlier standalone report"] = ROOT / "reports"
if choices:
    selected = st.selectbox("Select a run", list(choices))
    folder = choices[selected]
    status_file = folder / "pipeline-status.json"
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text())
            st.write(f"Tests: {status.get('tests', 'unknown')} · AI: {status.get('ai', 'unknown')}")
            if status.get("error"):
                st.error(status["error"])
        except (OSError, ValueError):
            st.info("Status is being written. Refresh shortly.")
    page = folder / "report.html"
    if page.exists():
        content = page.read_text(encoding="utf-8")
        st.download_button("Download HTML report", content, file_name=f"{selected}-report.html", mime="text/html")
        report_file = folder / "ai-report.json"
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {}
        evidence = report.get("measured_evidence", {})
        ai = report.get("ai_analysis", {})
        result = ai.get("result", {})
        columns = st.columns(3)
        columns[0].metric("AI analysis", ai.get("status", "Not recorded"))
        seconds = evidence.get("recovery_check_seconds")
        columns[1].metric("Link recovery check", f"{seconds:.1f} s" if isinstance(seconds, (int, float)) else "Not recorded")
        final = evidence.get("final_health", {})
        columns[2].metric("Final API health", "Healthy" if final.get("application_check", {}).get("matched", final.get("health") == {"status": "ok"}) else "Not verified")
        selected_scenario = evidence.get("scenario", "all")
        st.caption(f"Selected scenario: {selected_scenario}")
        st.caption(f"Recorded run: {report.get('source_run', 'Unknown')} · Model: {ai.get('model', 'Unknown')}")
        observations, explanations, details = st.tabs(["Measured observations", "AI explanation", "Evidence"])
        with observations:
            st.markdown("**Recorded test observations**")
            app = evidence.get("application_scenario", {})
            rows = []
            for name, value in [("Link interruption", evidence.get("fault_request", {})), ("Application interruption", app.get("http_during_fault", {}))]:
                observation = "Unavailable as expected" if value.get("reachable") is False else ("Unexpectedly reachable" if value.get("reachable") is True else "Not recorded")
                kind = "link" if name.startswith("Link") else "application"
                if selected_scenario not in ("all", kind):
                    observation = "Not selected"
                rows.append({"Scenario": name, "HTTP observation": observation})
            for row in rows:
                st.write(f"**{row['Scenario']}:** {row['HTTP observation']}")
            st.caption("Selected outages are intentional. These observations do not replace the pyATS test summary.")
            if evidence.get("cleanup_error"):
                st.error(evidence["cleanup_error"])
        with explanations:
            st.markdown("**AI analysis of this run**")
            st.caption("AI interpretation requires review. Test outcomes come from measured checks.")
            if ai.get("status") != "complete":
                st.warning(ai.get("error", "AI analysis incomplete."))
                st.info("Test evidence is available in the other tabs even when AI analysis fails.")
            else:
                st.write(result.get("summary", ""))
                for finding in result.get("findings", []):
                    with st.container(border=True):
                        st.write(finding.get("explanation", ""))
                        st.caption("Evidence: " + ", ".join(finding.get("evidence_refs", [])))
                for title, field in [("Suggested checks", "next_steps"), ("Limitations", "limitations")]:
                    st.markdown(f"**{title}**")
                    for item in result.get(field, []):
                        st.write("• " + item)
        with details:
            st.markdown("**Saved test evidence**")
            if evidence:
                with st.container(height=400):
                    st.json(evidence, expanded=1)
            else:
                st.info("No measured evidence is available for this report.")
    else:
        st.info("No HTML report yet. Review the execution log or refresh after the run finishes.")
else:
    st.info("No saved reports yet. Start a test run to create one.")
