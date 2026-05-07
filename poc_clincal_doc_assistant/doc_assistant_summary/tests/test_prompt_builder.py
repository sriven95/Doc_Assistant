"""
Unit tests for prompt_builder utility.
Tests prompt construction and summary chain formatting.
"""
import pytest
from app.utils.prompt_builder import build_prompt, format_summary_chain


SAMPLE_EVENTS = [
    {
        "event_id"           : "E003",
        "doc_type"           : "Discharge Planning",
        "plain_scrubbed_text": "Patient discharged with home health. SDOH: housing instability.",
    },
    {
        "event_id"           : "E002",
        "doc_type"           : "Case Management Narrative",
        "plain_scrubbed_text": "Follow-up visit. Patient reports food insecurity.",
    },
    {
        "event_id"           : "E001",
        "doc_type"           : "Discharge Planning Assessment",
        "plain_scrubbed_text": "Initial admission. Emergency contact: Jane Doe.",
    },
]


class TestBuildPrompt:
    def test_prompt_contains_system_instructions(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        assert "clinical documentation assistant" in prompt.lower()

    def test_prompt_contains_all_event_ids(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        for event in SAMPLE_EVENTS:
            assert event["event_id"] in prompt

    def test_prompt_contains_scrubbed_text(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        assert "housing instability" in prompt
        assert "food insecurity" in prompt

    def test_prompt_contains_doc_types(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        assert "Discharge Planning" in prompt

    def test_prompt_specifies_correct_event_count(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        assert str(len(SAMPLE_EVENTS)) in prompt

    def test_prompt_marks_first_as_most_recent(self):
        prompt = build_prompt(SAMPLE_EVENTS)
        assert "Most Recent" in prompt

    def test_empty_events_raises(self):
        with pytest.raises(Exception):
            build_prompt([])


class TestFormatSummaryChain:
    SUMMARIES = [
        "Most recent event summary text.",
        "Middle event summary text.",
        "Oldest event summary text.",
    ]
    EVENT_IDS = ["E003", "E002", "E001"]

    def test_chain_contains_all_event_ids(self):
        chain = format_summary_chain(self.SUMMARIES, self.EVENT_IDS)
        for eid in self.EVENT_IDS:
            assert eid in chain

    def test_first_event_labelled_most_recent(self):
        chain = format_summary_chain(self.SUMMARIES, self.EVENT_IDS)
        assert "Most Recent" in chain

    def test_last_event_labelled_oldest(self):
        chain = format_summary_chain(self.SUMMARIES, self.EVENT_IDS)
        assert "Oldest" in chain

    def test_chain_contains_summary_text(self):
        chain = format_summary_chain(self.SUMMARIES, self.EVENT_IDS)
        assert "Most recent event summary text." in chain
        assert "Oldest event summary text." in chain

    def test_single_event_chain(self):
        chain = format_summary_chain(["Only event."], ["E001"])
        assert "E001" in chain
        assert "Only event." in chain
