# NetApp Assure

An AI-assisted network and application regression testing project. It uses a local Docker lab to verify routing and API health, introduce controlled failures, check recovery, and explain the recorded evidence through a Streamlit dashboard.

## Features

- Automated OSPF neighbor, route, traceroute, and HTTP response checks.
- Selectable baseline, network-link failure, application failure, and combined scenarios.
- Restoration and recovery checks after each injected fault.
- Validated YAML test expectations and a configuration snapshot for each pipeline run.
- Required Groq AI analysis with evidence references and explicit failure reporting.
- Streamlit dashboard with background test execution, scrollable logs, and saved results.
- Downloadable HTML reports that separate measured observations from AI interpretation.
- GitHub Actions checks for API contracts, mocked AI/pipeline behavior, and the standalone Docker API.

## Use Cases

- **Regression testing:** repeat network and application checks after changes to the local lab.
- **Failure diagnosis practice:** distinguish a broken network path from an application outage on a healthy network.
- **Recovery verification:** confirm service returns after restoring a router link or restarting the API.
- **Learning and demonstration:** practice Python, pyATS, OSPF, Docker, and evidence-based troubleshooting without physical routers.

## Tech Stack

| Technology | Role |
| --- | --- |
| Python 3.12 | Test orchestration, configuration, and reporting |
| pyATS | Network test setup, scenarios, and cleanup |
| FRRouting (FRR) | Two virtual routers running OSPF |
| Docker and Docker Compose | Reproducible local network and application lab |
| FastAPI and Uvicorn | Sample API application |
| Streamlit | Dashboard and report viewer |
| Groq API | Hosted AI interpretation of selected test evidence |
| pytest and HTTPX | API tests and simulated provider/pipeline tests |
| YAML and Pydantic | Configuration and validation |
| Git and GitHub Actions | Version control and automated checks |
| Ubuntu / WSL2 | Linux execution environment |

## How It Works

```text
Test client --> FRR Router 1 --> FRR Router 2 --> Python API
                        OSPF routing
```

A run validates the configuration, checks baseline health, executes the selected fault scenario, restores the affected component, and checks final health. It then sends selected evidence to Groq and saves the analysis and HTML report.

| Scenario | What it tests |
| --- | --- |
| `baseline` | Healthy routing, expected network path, and API response; no injected outage |
| `link` | Baseline, router transit-link interruption, expected API outage, and recovery |
| `application` | Baseline, API stop while networking remains available, and recovery after restart |
| `all` | Both failure scenarios in sequence, including baseline and recovery checks |

An intentional outage is expected during fault testing. Tests pass when observations match expectations. AI explains evidence; it does not decide the test outcome or control the lab.

## Project Structure

```text
NetApp-Assure/
|-- app/                       # Sample FastAPI application
|-- config/lab.yaml            # Validated test expectations
|-- lab/                       # FRR configuration and lab host image
|-- scripts/
|   |-- start_dashboard.py     # Background dashboard launcher
|   |-- run_project.py         # Test and AI pipeline
|   |-- network_suite.py       # pyATS fault and recovery scenarios
|   |-- check_lab.py           # Routing and API baseline checks
|   |-- ai_report.py           # Groq analysis and report generation
|   |-- report_view.py         # HTML report rendering
|   |-- lab_config.py          # Configuration validation
|   `-- ...                    # Dashboard and diagnostic helpers
|-- tests/                     # Automated tests
|-- docs/screenshots/          # Project screenshots
|-- .github/workflows/ci.yml   # GitHub Actions workflow
|-- dashboard.py              # Streamlit interface
|-- compose.lab.yaml          # Routed FRR test lab
|-- compose.yaml              # Separate standalone API demo
|-- Dockerfile                # API image
|-- requirements*.txt         # Application, test, network, and UI dependencies
`-- reports/                  # Generated locally; excluded from Git
```

## Installation & Setup

### Prerequisites

The development environment is Ubuntu 24.04 on Windows through WSL2, with Python 3.12 and Docker Desktop WSL integration. The launcher and pipeline require Linux. Other environments have not been fully validated.

Install Git, Python 3.12 with `venv` support, and Docker with a Compose version supporting `interface_name`. Verify that `docker compose version` and `docker run --rm hello-world` work in Ubuntu. You also need internet access and your own Groq API key for the required AI stage.

Run the following commands in an Ubuntu terminal.

### 1. Clone and install dependencies

```bash
git clone https://github.com/vnagaven2003/NetApp-Assure.git
cd NetApp-Assure
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-ui.txt
```

If Ubuntu reports missing virtual environment support, install it with `sudo apt install python3-venv` and retry creating the environment.

### 2. Configure AI access

Enter your key at the hidden prompt; do not put it in source files or commit it:

```bash
read -rsp "Groq API key: " GROQ_API_KEY; echo
export GROQ_API_KEY
```

The configured default model is `qwen/qwen3.8-27b`. Availability and account permissions can change. To inspect available models or override the default:

```bash
python scripts/list_ai_models.py
# Replace MODEL_ID with a model supporting the JSON output required by the script.
export GROQ_MODEL="MODEL_ID"
```

Only set `GROQ_MODEL` when overriding the default. Model listing does not guarantee permission to run inference. Selected lab evidence is sent to Groq for analysis.

### 3. Start and verify the lab

Keep Docker running, then execute:

```bash
docker compose -f compose.lab.yaml up --build -d --wait
python scripts/run_project.py --validate-config
python scripts/check_lab.py
```

The lab uses `10.101.1.0/24`, `10.101.12.0/24`, and `10.101.2.0/24`; avoid conflicting Docker networks. The routed API is accessed through the lab client, not a published host port.

### 4. Launch the dashboard

From the same terminal where the key is exported:

```bash
python scripts/start_dashboard.py
```

Open **http://127.0.0.1:8501**. The launcher returns the terminal prompt and prints the server PID and stop command. It inherits the key without saving it to disk. Restart it after Windows restarts or WSL shuts down. If a foreground dashboard already occupies port 8501, stop it with Ctrl+C before using the background launcher.

For later sessions, activate `.venv`, export your key again if needed, start the lab, and launch the dashboard. Server logs are in `reports/dashboard-server.log`.

## Usage

1. Confirm the dashboard shows the lab containers running and an AI credential set.
2. Select `baseline` for the first run, or another scenario from the table above.
3. Click **Run tests and AI analysis** and follow the execution log.
4. When finished, click **Refresh report list** and select the newest run.
5. Review **Measured observations**, **AI explanation**, and **Evidence**, or download the HTML report.

A credential marked **Set** only confirms its presence; the API call validates access. Test status and AI completion are separate. A failed AI request leaves the workflow incomplete while preserving measured evidence.

### Command-line alternative

With the lab running, environment activated, and key exported:

```bash
python scripts/run_project.py --scenario baseline
python scripts/run_project.py --scenario all
```

Edit `config/lab.yaml` to change expected OSPF peers/routes, HTTP path/status/JSON response, traceroute hops, and timeouts. These settings change test expectations, not router configuration. Use `--config path/to/config.yaml` to select another file. Fault targets remain the fixed Docker lab.

Each pipeline run saves evidence, a configuration snapshot, AI output, an HTML report, and pipeline status under `reports/runs/<run-id>/`.

### Troubleshooting and cleanup

If AI fails, fix the reported model, credential, connectivity, or quota issue and retry analysis without repeating the outage. Replace `<run-id>` with the actual folder name:

```bash
NETAPP_REPORT_DIR="$PWD/reports/runs/<run-id>" python scripts/ai_report.py
```

This updates the AI report; `pipeline-status.json` still describes the original pipeline attempt.

Do not run the standalone fault suite concurrently with a dashboard or CLI pipeline. If a run is forcibly interrupted, restore the lab and check health:

```bash
docker compose -f compose.lab.yaml exec r1 ip link set eth1 up
docker compose -f compose.lab.yaml start api
python scripts/check_lab.py
```

After all tests finish, stop the lab with:

```bash
docker compose -f compose.lab.yaml down
```

## Testing

```bash
python -m pytest -q
```

[GitHub Actions](https://github.com/vnagaven2003/NetApp-Assure/actions) runs API and mocked AI/pipeline tests, validates Compose files, and builds and checks the standalone API. CI needs no Groq key and does not run the FRR fault suite or live AI analysis. Those are separate local integration checks.

## Screenshots

These examples show successful baseline and application runs, not proof of a completed `all` run.

### Dashboard

![Dashboard scenario selection and readiness](docs/screenshots/User%20attachment.png)

### Baseline report

No faults were selected, so link recovery is not recorded.

![Baseline HTML report](docs/screenshots/Report_screenshot.png)

### Baseline AI interpretation

The AI statement "no packet loss" exceeds what the traceroute check proves; the check verifies the observed hop path, not packet loss.

![Baseline AI interpretation](docs/screenshots/Report_screenshot1.png)

### Application results

Tests passed, AI completed, and the API recovered. Link recovery is not recorded for an application-only run.

![Application results](docs/screenshots/results_interface.png)

### Application AI explanation

![Application outage and recovery explanation](docs/screenshots/AI_Explanation.png)

## Scope & Limitations

- Supports the fixed local Docker lab. Physical Cisco switches and routers require additional adapters and validation.
- The topology has one routed path; the link scenario tests outage and restoration, not backup-path failover.
- Checks are sampled observations, not continuous monitoring or performance measurements.
- AI evidence references are validated, but the explanation still requires human review.
- The API inventory is sample data, not discovered devices. The dashboard is intended for local use.
