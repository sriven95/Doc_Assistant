"""
Unit tests for excel_service.
Tests read/write operations using a temporary Excel file.
"""
import os
import pytest
import pandas as pd
from unittest.mock import patch

from app.services.excel_service import (
    get_all_patients,
    get_events_for_patient,
    get_single_event,
    get_existing_summary,
    write_summary,
)


def make_test_df():
    """Create a minimal valid input DataFrame for testing."""
    return pd.DataFrame([
        {
            "event_id"          : "E001",
            "person_id"         : "P001",
            "doc_type"          : "Discharge Planning",
            "plain_scrubbed_text": "Patient note one.",
            "run_id"            : "R1",
            "model_id"          : "gemini",
            "model_processed_at": "2025-01-01",
        },
        {
            "event_id"          : "E002",
            "person_id"         : "P001",
            "doc_type"          : "Case Management",
            "plain_scrubbed_text": "Patient note two.",
            "run_id"            : "R1",
            "model_id"          : "gemini",
            "model_processed_at": "2025-02-01",
        },
        {
            "event_id"          : "E003",
            "person_id"         : "P002",
            "doc_type"          : "Discharge Planning",
            "plain_scrubbed_text": "Second patient note.",
            "run_id"            : "R1",
            "model_id"          : "gemini",
            "model_processed_at": "2025-01-15",
        },
    ])


class TestGetAllPatients:
    def test_groups_by_person_id(self, tmp_path):
        df = make_test_df()
        path = str(tmp_path / "input.xlsx")
        df.to_excel(path, index=False)

        patients = get_all_patients(path)
        assert "P001" in patients
        assert "P002" in patients
        assert len(patients["P001"]) == 2
        assert len(patients["P002"]) == 1

    def test_preserves_row_order(self, tmp_path):
        df = make_test_df()
        path = str(tmp_path / "input.xlsx")
        df.to_excel(path, index=False)

        patients = get_all_patients(path)
        event_ids = [e["event_id"] for e in patients["P001"]]
        assert event_ids == ["E001", "E002"]

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            get_all_patients("nonexistent/path.xlsx")


class TestGetSingleEvent:
    def test_returns_correct_event(self, tmp_path):
        df = make_test_df()
        path = str(tmp_path / "input.xlsx")
        df.to_excel(path, index=False)

        event = get_single_event("E003", path)
        assert event is not None
        assert event["event_id"] == "E003"
        assert event["plain_scrubbed_text"] == "Second patient note."

    def test_returns_none_for_missing_event(self, tmp_path):
        df = make_test_df()
        path = str(tmp_path / "input.xlsx")
        df.to_excel(path, index=False)

        event = get_single_event("E999", path)
        assert event is None


class TestWriteAndReadSummary:
    def test_write_creates_output(self, tmp_path):
        out_path = str(tmp_path / "output.xlsx")
        with patch("app.services.excel_service.settings") as mock_settings:
            mock_settings.output_file        = out_path
            mock_settings.out_person_id      = "person_id"
            mock_settings.out_main_subject   = "main_subject"
            mock_settings.out_summary_chain  = "summary_chain"
            mock_settings.out_processed_events = "processed_event_ids"
            mock_settings.out_event_count    = "event_count"
            mock_settings.out_model_id       = "model_id"
            mock_settings.out_generated_at   = "generated_at"
            mock_settings.out_last_updated_at= "last_updated_at"
            mock_settings.gemini_model       = "gemini-2.5-flash"

            write_summary(
                person_id           = "P001",
                main_subject        = "Test subject.",
                summary_chain       = "[Event: E001 | Most Recent]\nSummary.",
                processed_event_ids = ["E001"],
            )
            assert os.path.exists(out_path)
