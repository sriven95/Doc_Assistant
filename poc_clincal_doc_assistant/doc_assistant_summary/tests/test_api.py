"""
Integration tests for the FastAPI endpoints.
Uses httpx TestClient — no real Gemini calls are made.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.schemas import SummaryResponse, JobStatusResponse


@pytest.fixture
def mock_summary_response():
    return SummaryResponse(
        person_id           = "P001",
        status              = "created",
        main_subject        = "Patient has housing instability and food insecurity.",
        summary_chain       = "[Event: E001 | Most Recent]\nPatient admitted.",
        processed_event_ids = ["E001"],
        event_count         = 1,
        model_id            = "gemini-2.5-flash",
        generated_at        = "2025-01-01T00:00:00",
        last_updated_at     = "2025-01-01T00:00:00",
    )


@pytest.fixture
def mock_job_response():
    return JobStatusResponse(
        job_id         = "test-job-123",
        status         = "queued",
        total_patients = 0,
        processed      = 0,
        failed         = 0,
        message        = "Bulk generation started.",
    )


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()


@pytest.mark.asyncio
async def test_generate_summaries(mock_job_response):
    with patch(
        "app.api.v1.routes.summary.start_bulk_job",
        return_value=mock_job_response,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/generate-summaries",
                json={},
            )
    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_update_summary(mock_summary_response):
    with patch(
        "app.api.v1.routes.summary.update_patient_summary",
        new_callable=AsyncMock,
        return_value=mock_summary_response,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/update-summary",
                json={"person_id": "P001", "event_id": "E001"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["person_id"] == "P001"
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_get_summary_not_found():
    with patch(
        "app.api.v1.routes.summary.get_summary",
        new_callable=AsyncMock,
        return_value=SummaryResponse(
            person_id="P999",
            status="not_found",
            message="No summary found.",
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/summary/P999")
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"


@pytest.mark.asyncio
async def test_job_status_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/status/nonexistent-job")
    assert response.status_code == 404
