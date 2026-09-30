"""Offline HTML presentation of measured evidence and saved AI analysis."""
import html
import json
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True)


def render(report):
    evidence = report.get("measured_evidence", {})
    ai = report.get("ai_analysis", {})
    result = ai.get("result", {})
    if not isinstance(result, dict):
        result = {}
    app = evidence.get("application_scenario", {})
    def health(value):
        matched = value.get("application_check", {}).get("matched", value.get("health") == {"status": "ok"})
        return "Healthy response recorded" if matched else "Not verified"
    def unreachable(value):
        if value.get("reachable") is False:
            return "HTTP unavailable as expected"
        if value.get("reachable") is True:
            return "Unexpected: HTTP remained reachable"
        return "Not recorded"
    rows = [
        ("Baseline", "Network and application available", health(evidence.get("baseline", {}))),
        ("Link interruption", "Router 1 transit interface disabled", unreachable(evidence.get("fault_request", {}))),
        ("Link recovery", "Restore interface and wait for routing", health(evidence.get("recovery", {}))),
        ("Application interruption", "Stop API while retaining its network", unreachable(app.get("http_during_fault", {}))),
        ("Application recovery", "Restart API", health(app.get("recovery", {}))),
        ("Final health", "Verify lab after cleanup", health(evidence.get("final_health", {}))),
    ]
    scenario = evidence.get("scenario", "all")
    rows = [(name, action, "Not selected" if
             (name.startswith("Link") and scenario not in ("all", "link")) or
             (name.startswith("Application") and scenario not in ("all", "application"))
             else observation) for name, action, observation in rows]
    table = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in row) + "</tr>" for row in rows)
    findings = "".join(f"<article><p>{esc(f.get('explanation', ''))}</p><small>Evidence: " +
        ", ".join(f'<a href="#e-{esc(ref)}">{esc(ref)}</a>' for ref in f.get("evidence_refs", []) if ref in evidence) +
        "</small></article>" for f in result.get("findings", []))
    def bullets(values):
        return "<ul>" + "".join(f"<li>{esc(v)}</li>" for v in values) + "</ul>"
    details = "".join(f'<details id="e-{esc(key)}"><summary>{esc(key)}</summary><pre>{esc(json.dumps(value, indent=2))}</pre></details>'
                      for key, value in evidence.items())
    status = "AI analysis complete" if ai.get("status") == "complete" else "AI analysis incomplete"
    elapsed = evidence.get("recovery_check_seconds")
    timing = f"{elapsed:.2f} seconds" if isinstance(elapsed, (float, int)) else "Not recorded"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>NetApp Assure report</title>
<style>body{{font:16px/1.6 system-ui;background:#0f172a;color:#e2e8f0;margin:0}}main{{max-width:1050px;margin:auto;padding:32px 20px}}h1{{font-size:36px;color:#67e8f9;margin-bottom:0}}h2{{margin-top:32px}}small,.muted{{color:#cbd5e1}}section,article,.card,details{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin:12px 0}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.card strong{{display:block;font-size:20px}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #475569}}.scroll{{overflow:auto}}a{{color:#67e8f9}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}summary{{cursor:pointer}}.note{{border-left:4px solid #fbbf24;padding-left:15px}}@media print{{body{{background:white;color:black}}section,article,.card,details{{background:white;color:black}}a,h1{{color:#075985}}}}</style></head>
<body><main><h1>NetApp Assure</h1><p class="muted">Network and application regression report</p>
<p>Test run: {esc(report.get('source_run', 'Unknown'))}</p>
<p>Test process: {esc(report.get('pipeline', {}).get('tests', 'See pyATS console'))} · AI stage: {esc(ai.get('status', 'incomplete'))}</p>
<div class="cards"><div class="card"><small>Required AI stage</small><strong>{status}</strong>{esc(ai.get('model', 'Not selected'))}</div>
<div class="card"><small>Recorded link recovery check</small><strong>{esc(timing)}</strong>Measured after the restore command</div>
<div class="card"><small>Final lab observation</small><strong>{esc(health(evidence.get('final_health', {})))}</strong></div></div>
<h2>Measured scenario evidence</h2><p>Client → Router 1 → Router 2 → API</p>
<div class="scroll"><table><thead><tr><th>Stage</th><th>Action or expectation</th><th>Recorded observation</th></tr></thead><tbody>{table}</tbody></table></div>
<p class="note">Selected scenario: {esc(scenario)}. These observations do not replace the pyATS test summary. Missing evidence is not a pass. Selected interruptions are deliberate.</p>
<p>Cleanup error: {esc(evidence.get('cleanup_error', 'None recorded'))}</p>
<h2>AI interpretation</h2><p class="note">AI explanations are suggestions. Evidence references are validated, but the reasoning still requires review. An expected outage is not itself a failed test.</p>
<section><p>{esc(result.get('summary', ai.get('error', 'No analysis available')))}</p></section>{findings}
<h3>Suggested next checks</h3>{bullets(result.get('next_steps', []))}
<h3>AI-stated limitations</h3>{bullets(result.get('limitations', []))}
<h2>Inspect measured evidence</h2>{details}
<details><summary>Full saved report</summary><pre>{esc(json.dumps(report, indent=2))}</pre></details>
<p class="muted">Generated locally from saved evidence and analysis. This page makes no network requests.</p></main></body></html>'''


if __name__ == "__main__":
    directory = Path(__file__).resolve().parents[1] / "reports"
    report = json.loads((directory / "ai-report.json").read_text(encoding="utf-8"))
    (directory / "report.html").write_text(render(report), encoding="utf-8")
    print(f"Rendered {directory / 'report.html'} — no API call made.")
