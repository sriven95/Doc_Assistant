from typing import List, Dict


SYSTEM_PROMPT = """
You are a clinical documentation assistant specializing in case management.
Your job is to read clinical notes and produce a clear, structured patient summary.

Rules you must follow:
- Answer strictly from the provided notes only. Do not guess or infer.
- Never include patient names, MRNs, SSNs, or any personal identifiers.
- Be concise but complete — capture every clinically important detail.
- Always respond in valid JSON format exactly as instructed.
""".strip()


def build_prompt(events: List[Dict]) -> str:
    """
    Build a Gemini prompt for a patient given their list of events.

    events : list of dicts ordered newest → oldest, each containing:
             event_id, doc_type, plain_scrubbed_text

    Returns the full prompt string ready to send to Gemini.
    """
    events_block = ""
    for idx, event in enumerate(events, start=1):
        label = "Most Recent" if idx == 1 else f"Event {idx}"
        events_block += f"""
--- Event {idx} ({label}) ---
Document Type : {event.get("doc_type", "N/A")}
Event ID      : {event.get("event_id", "N/A")}
Clinical Note :
{event.get("plain_scrubbed_text", "").strip()}
""".strip() + "\n\n"

    return f"""
{SYSTEM_PROMPT}

Below are clinical notes for one patient.
Events are ordered NEWEST first (Event 1) to OLDEST last.

{events_block.strip()}

Generate a structured patient summary in the following JSON format:

{{
  "main_subject": "A single paragraph summarizing the overall clinical picture of this patient across all events. Cover key SDOH risks, medical conditions, support systems, and care coordination needs.",
  "event_summaries": [
    "Summary of Event 1 (most recent) — 3 to 5 sentences covering key clinical details, SDOH factors, emergency contacts, home health, and action items.",
    "Summary of Event 2 — same format.",
    "... one entry per event in the same newest to oldest order ..."
  ]
}}

Important:
- event_summaries must have exactly {len(events)} entries — one per event in order.
- Return ONLY the JSON object. No extra text, no markdown, no code blocks.
""".strip()


def format_summary_chain(event_summaries: List[str], event_ids: List[str]) -> str:
    """
    Convert event summaries into a readable chain string for Excel storage.

    Format:
        [Event: E003 | Most Recent]
        Summary text...

        [Event: E002]
        Summary text...

        [Event: E001 | Oldest]
        Summary text...
    """
    chain_parts = []
    total = len(event_summaries)

    for idx, (summary, event_id) in enumerate(zip(event_summaries, event_ids)):
        if idx == 0:
            label = f"[Event: {event_id} | Most Recent]"
        elif idx == total - 1:
            label = f"[Event: {event_id} | Oldest]"
        else:
            label = f"[Event: {event_id}]"

        chain_parts.append(f"{label}\n{summary.strip()}")

    return "\n\n".join(chain_parts)
