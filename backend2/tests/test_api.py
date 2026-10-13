from typing import Any, Dict
from fastapi.testclient import TestClient
import pytest

from ai.ai_engine import generate_interpretations
from backend2.main import app, set_ai_engine_provider
from backend2.schemas import (
    Action,
    AnalyzeRequest,
    CandidateAmbiguity,
    CandidateInterpretation,
)

HEALTH_ENDPOINT = "/api/health"
ANALYZE_ENDPOINT = "/api/analyze"

HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNPROCESSABLE = 422

EXPECTED_BRANCH_COUNT = 3
PRIMARY_BENCHMARK_INSTRUCTION = "Delete old user records."
SECONDARY_BENCHMARK_INSTRUCTION = "Remove inactive users."
OUT_OF_SCOPE_INSTRUCTION = "Restore the latest backup if necessary."
BLANK_INSTRUCTION = "   "
UNSUPPORTED_SCENARIO = "unsupported_scenario"
STANDARD_SCENARIO = "user_cleanup"

CORS_ORIGIN_HEADER_KEY = "access-control-allow-origin"
TEST_ORIGIN_DEV_CLIENT = "http://localhost:3000"


@pytest.fixture
def client() -> TestClient:
    set_ai_engine_provider(None)
    with TestClient(app) as test_client:
        yield test_client
    set_ai_engine_provider(generate_interpretations)


def test_health_endpoint_returns_ok_status(client: TestClient):
    response = client.get(HEALTH_ENDPOINT)
    assert response.status_code == HTTP_STATUS_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "semantic-chaos-monkey"
    assert "version" in data


def test_analyze_primary_benchmark_executes_successfully(client: TestClient):
    request_model = AnalyzeRequest(
        instruction=PRIMARY_BENCHMARK_INSTRUCTION,
        scenario=STANDARD_SCENARIO,
    )
    response = client.post(ANALYZE_ENDPOINT, json=request_model.model_dump())

    assert response.status_code == HTTP_STATUS_OK
    data = response.json()

    assert data["status"] == "ok"
    assert data["instruction"] == PRIMARY_BENCHMARK_INSTRUCTION
    assert data["scenario"] == STANDARD_SCENARIO
    assert len(data["interpretations"]) == EXPECTED_BRANCH_COUNT
    assert data["outcomes_diverge"] is True
    assert len(data["ambiguities"]) >= 1
    assert len(data["suggested_rewrite"]) > 0

    # Ensure simulator computed true affected IDs across 500 records
    interp_map = {i["id"]: i for i in data["interpretations"]}
    assert interp_map["A"]["affected_count"] == 120
    assert interp_map["B"]["affected_count"] == 360
    assert interp_map["C"]["affected_count"] == 160

    # Ensure blast radius is accurately computed
    assert interp_map["A"]["blast_radius"]["mrr_at_risk"] == 0
    assert interp_map["B"]["blast_radius"]["mrr_at_risk"] >= 500000
    assert interp_map["B"]["blast_radius"]["enterprise_accounts_lost"] == 40
    assert interp_map["C"]["blast_radius"]["enterprise_accounts_lost"] == 10

    # Verify ambiguities confirmed divergence and provide evidence
    assert len(data["ambiguities"]) >= 1
    assert data["ambiguities"][0]["observed_risk"] is True
    assert len(data["ambiguities"][0]["evidence"]) > 0


def test_analyze_secondary_benchmark_executes_successfully(client: TestClient):
    request_model = AnalyzeRequest(
        instruction=SECONDARY_BENCHMARK_INSTRUCTION,
        scenario=STANDARD_SCENARIO,
    )
    response = client.post(ANALYZE_ENDPOINT, json=request_model.model_dump())

    assert response.status_code == HTTP_STATUS_OK
    data = response.json()

    assert data["status"] == "ok"
    assert len(data["interpretations"]) == EXPECTED_BRANCH_COUNT
    assert data["outcomes_diverge"] is True


def test_analyze_out_of_scope_instruction_returns_unsupported_status(client: TestClient):
    request_model = AnalyzeRequest(
        instruction=OUT_OF_SCOPE_INSTRUCTION,
        scenario=STANDARD_SCENARIO,
    )
    response = client.post(ANALYZE_ENDPOINT, json=request_model.model_dump())

    assert response.status_code == HTTP_STATUS_OK
    data = response.json()

    assert data["status"] == "unsupported"
    assert data["interpretations"] == []
    assert data["ambiguities"] == []
    assert data["outcomes_diverge"] is False
    assert "reason" in data and len(data["reason"]) > 0


def test_analyze_unsupported_scenario_returns_bad_request(client: TestClient):
    payload = {
        "instruction": PRIMARY_BENCHMARK_INSTRUCTION,
        "scenario": UNSUPPORTED_SCENARIO,
    }
    response = client.post(ANALYZE_ENDPOINT, json=payload)

    assert response.status_code == HTTP_STATUS_BAD_REQUEST
    error_data = response.json()
    assert "detail" in error_data
    assert UNSUPPORTED_SCENARIO in error_data["detail"]


def test_analyze_blank_instruction_returns_validation_error(client: TestClient):
    payload = {
        "instruction": BLANK_INSTRUCTION,
        "scenario": STANDARD_SCENARIO,
    }
    response = client.post(ANALYZE_ENDPOINT, json=payload)

    assert response.status_code == HTTP_STATUS_UNPROCESSABLE


def test_analyze_missing_instruction_field_returns_validation_error(client: TestClient):
    payload = {
        "scenario": STANDARD_SCENARIO,
    }
    response = client.post(ANALYZE_ENDPOINT, json=payload)

    assert response.status_code == HTTP_STATUS_UNPROCESSABLE


def test_analyze_malformed_ai_output_insufficient_branches_triggers_422(client: TestClient):
    # Mock AI engine returning only 2 interpretations instead of 3
    def mock_bad_ai(instruction: str, scenario: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "interpretations": [
                CandidateInterpretation(
                    id="A",
                    title="Interp A",
                    assumption="Assumption A",
                    action=Action(type="delete_users", condition="inactive_90_days"),
                    explanation="Explanation A",
                ),
                CandidateInterpretation(
                    id="B",
                    title="Interp B",
                    assumption="Assumption B",
                    action=Action(type="delete_users", condition="created_90_days"),
                    explanation="Explanation B",
                ),
            ],
            "candidate_ambiguities": [],
            "suggested_rewrite": "Rewrite this properly.",
        }

    set_ai_engine_provider(mock_bad_ai)

    request_model = AnalyzeRequest(
        instruction=PRIMARY_BENCHMARK_INSTRUCTION,
        scenario=STANDARD_SCENARIO,
    )
    response = client.post(ANALYZE_ENDPOINT, json=request_model.model_dump())

    assert response.status_code == HTTP_STATUS_UNPROCESSABLE
    assert "exactly 3" in response.json()["detail"]


def test_cors_headers_present_for_allowed_origins(client: TestClient):
    response = client.get(
        HEALTH_ENDPOINT,
        headers={"Origin": TEST_ORIGIN_DEV_CLIENT},
    )

    assert response.status_code == HTTP_STATUS_OK
    assert CORS_ORIGIN_HEADER_KEY in response.headers
    assert response.headers[CORS_ORIGIN_HEADER_KEY] == TEST_ORIGIN_DEV_CLIENT


def test_plugged_in_ai_engine_integrates_successfully(client: TestClient):
    set_ai_engine_provider(generate_interpretations)

    request_model = AnalyzeRequest(
        instruction=PRIMARY_BENCHMARK_INSTRUCTION,
        scenario=STANDARD_SCENARIO,
    )
    response = client.post(ANALYZE_ENDPOINT, json=request_model.model_dump())

    assert response.status_code == HTTP_STATUS_OK
    data = response.json()

    assert data["status"] == "ok"
    assert len(data["interpretations"]) == EXPECTED_BRANCH_COUNT
    assert data["outcomes_diverge"] is True
    assert len(data["ambiguities"]) >= 1
    assert data["ambiguities"][0]["observed_risk"] is True

