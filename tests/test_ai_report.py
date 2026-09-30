import json
import httpx
import pytest
from scripts.ai_report import analyse, render


def test_compact_evidence_preserves_facts_without_mutating_source():
    from scripts.ai_report import compact_evidence
    raw = {"neighbors": [{"nbrState": "Full/DR", "upTimeInMsec": 999}],
           "route": [{"prefix": "10.101.2.0/24", "protocol": "ospf", "installed": True,
                      "internalFlags": 8}], "health": {"status": "ok"}}
    result = compact_evidence(raw)
    assert result["neighbors"] == [{"nbrState": "Full/DR"}]
    assert result["route"][0]["installed"] is True
    assert "internalFlags" not in result["route"][0]
    assert result["health"] == raw["health"]
    assert raw["neighbors"][0]["upTimeInMsec"] == 999


def response(ref="baseline"):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "summary": "Lab evidence", "findings": [{"explanation": "Baseline observed", "evidence_refs": [ref]}],
        "next_steps": [], "limitations": ["Not a hardware test"]})}}]}


def test_valid_analysis_and_selected_evidence():
    def handler(request):
        sent = json.loads(request.content)
        assert "private_extra" not in sent["messages"][1]["content"]
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json=response())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = analyse({"started_at": "test", "baseline": {}, "private_extra": "excluded"}, "test-key", "test-model", client)
    assert result["summary"] == "Lab evidence"


@pytest.mark.parametrize("status,body", [(401, {}), (429, {}), (200, response("invented")), (200, {})])
def test_failed_or_ungrounded_response_rejected(status, body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body))) as client:
        with pytest.raises(ValueError):
            analyse({"started_at": "test", "baseline": {}}, "test-key", "test-model", client)


def test_missing_key_does_not_call_provider():
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected request"))) as client:
        with pytest.raises(ValueError, match="missing"):
            analyse({}, "", "test-model", client)


def test_report_escapes_model_html():
    output = render({"ai_analysis": {"status": "complete", "result": "<script>alert(1)</script>"}})
    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_empty_report_does_not_claim_healthy_or_passing():
    output = render({"ai_analysis": {"status": "incomplete"}})
    assert "Not verified" in output
    assert "AI analysis incomplete" in output
    assert "Healthy response recorded" not in output


def test_observations_separate_from_ai():
    output = render({"measured_evidence": {"fault_request": {"reachable": True}},
                     "ai_analysis": {"status": "complete", "result": {"summary": "All fine"}}})
    assert "Unexpected: HTTP remained reachable" in output
    assert "AI interpretation" in output


def test_qwen_schema_and_reasoning_settings():
    def handler(request):
        sent = json.loads(request.content)
        assert sent["reasoning_effort"] == "none"
        schema = sent["response_format"]["json_schema"]
        assert schema["strict"] is True
        refs = schema["schema"]["properties"]["findings"]["items"]["properties"]["evidence_refs"]
        assert refs["items"]["enum"] == ["started_at", "baseline"]
        return httpx.Response(200, json=response())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        analyse({"started_at": "test", "baseline": {}}, "test-key", "qwen/qwen3.8-27b", client)


def test_truncation_has_specific_diagnostic():
    body = response()
    body["choices"][0]["finish_reason"] = "length"
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
        with pytest.raises(ValueError, match="cut short"):
            analyse({"started_at": "test"}, "test-key", "test-model", client)


@pytest.mark.parametrize("status,expected", [(401, "Authentication failed"), (429, "quota exceeded"), (403, "Access denied")])
def test_safe_specific_provider_errors(status, expected):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json={"error": {"message": "secret-value"}}))) as client:
        with pytest.raises(ValueError) as error:
            analyse({"started_at": "test"}, "test-key", "test-model", client)
    assert expected in str(error.value)
    assert "secret-value" not in str(error.value)
    assert "test-key" not in str(error.value)
