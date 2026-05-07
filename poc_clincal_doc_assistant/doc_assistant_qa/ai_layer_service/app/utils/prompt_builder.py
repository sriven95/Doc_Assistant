from typing import List, Dict


SYSTEM_PROMPT = """
You are a clinical documentation assistant helping healthcare staff understand patient records.

You have two modes — choose automatically based on the message:

MODE 1 — CONVERSATIONAL (for greetings, acknowledgements, thanks, casual messages):
Examples: "Ok", "Thanks", "Bye", "Got it", "Ohh k", "Sure", "Hello", "Great"
→ Respond naturally, briefly, and warmly like a helpful assistant.
→ Do NOT reference clinical notes for these messages.
→ Keep it to 1 short sentence max.

MODE 2 — CLINICAL QUESTION (for questions about the patient's records):
Examples: "What SDOH risks?", "Who is the emergency contact?", "What is the discharge plan?"
→ Answer ONLY from the provided clinical context chunks below.
→ If the answer is not in the context, say: "This information is not available in the patient's clinical notes."
→ Never guess, infer, or make up clinical information.
→ Never include patient names, MRNs, SSNs, or any personal identifiers.
→ Be concise, clear, and clinically accurate.
→ Use prior conversation history and prior RAG context for follow-up understanding.

Always choose the right mode. Never give a robotic or repetitive response.
""".strip()


def _format_chunks(chunks: List[Dict], label: str) -> str:
    """Format a list of chunks into a labelled block for the prompt."""
    if not chunks:
        return ""
    block = f"\n--- {label} ---\n"
    for idx, chunk in enumerate(chunks, start=1):
        doc_type = chunk.get("doc_type", "N/A")
        # Handle nan values from Excel
        if str(doc_type).lower() in ("nan", "none", ""):
            doc_type = "Clinical Note"
        block += (
            f"[Source {idx} | Event: {chunk.get('event_id', 'N/A')} | "
            f"Type: {doc_type}]\n"
            f"{chunk.get('text', '').strip()}\n\n"
        )
    return block.rstrip()


def build_qa_prompt(
    question: str,
    context_chunks: List[Dict],
    history: List[Dict],
    rag_history: List[List[Dict]] = None,
    main_subject: str = "",  
) -> str:
    """
    Build the full Gemini prompt.

    Includes:
    - Smart system prompt (conversational vs clinical mode)
    - Current RAG chunks (most relevant to this question)
    - Previous RAG turns (sliding window — up to 2 historical turns)
    - Conversation history (last 20 turns)
    - Current question
    """
    rag_history = rag_history or []

    # Add this block before the RAG context
    patient_context_block = ""
    if main_subject and main_subject.strip():
        patient_context_block = (
            f"--- Patient Overview (generated summary) ---\n"
            f"{main_subject.strip()}\n"
        )

    # ── Current RAG chunks ────────────────────────────────────────
    current_rag_block = _format_chunks(
        context_chunks,
        "Current Clinical Context (most relevant to this question)"
    )

    # ── Previous RAG turns ────────────────────────────────────────
    prev_rag_block = ""
    if rag_history:
        total_prev = len(rag_history)
        for turn_idx, past_chunks in enumerate(rag_history):
            turns_ago = total_prev - turn_idx
            label     = (
                f"Previous Clinical Context "
                f"({'1 turn ago' if turns_ago == 1 else f'{turns_ago} turns ago'})"
            )
            prev_rag_block += _format_chunks(past_chunks, label) + "\n"

    # ── Conversation history ──────────────────────────────────────
    history_block = ""
    if history:
        history_block = "\n--- Conversation History ---\n"
        for turn in history:
            role    = turn.get("role", "user")
            content = turn.get("content", "")
            prefix  = "Clinical Staff" if role == "user" else "Assistant"
            history_block += f"{prefix}: {content}\n"

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{patient_context_block}\n"   # ← ADD THIS LINE
        f"{current_rag_block}\n\n"
        f"{prev_rag_block}"
        f"{history_block}\n"
        f"--- Current Message ---\n"
        f"Clinical Staff: {question}\n\n"
        f"Assistant:"
    )