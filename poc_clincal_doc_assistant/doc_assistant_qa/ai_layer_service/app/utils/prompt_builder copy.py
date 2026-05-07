from typing import List, Dict


SYSTEM_PROMPT = """
You are a clinical documentation assistant helping healthcare staff understand patient records.

Rules you must follow strictly:
- Answer ONLY from the provided clinical context chunks below.
- If the answer is not in the context, say: "This information is not available in the patient's clinical notes."
- Never guess, infer, or make up clinical information.
- Never include patient names, MRNs, SSNs, or any personal identifiers in your answer.
- Be concise, clear, and clinically accurate.
- You may use prior conversation history and prior RAG context for follow-up understanding.
""".strip()


def _format_chunks(chunks: List[Dict], label: str) -> str:
    """
    Format a list of chunks into a labelled block for the prompt.
    """
    if not chunks:
        return ""
    block = f"\n--- {label} ---\n"
    for idx, chunk in enumerate(chunks, start=1):
        block += (
            f"[Source {idx} | Event: {chunk.get('event_id', 'N/A')} | "
            f"Type: {chunk.get('doc_type', 'N/A')}]\n"
            f"{chunk.get('text', '').strip()}\n\n"
        )
    return block.rstrip()


def build_qa_prompt(
    question: str,
    context_chunks: List[Dict],
    history: List[Dict],
    rag_history: List[List[Dict]] = None,
) -> str:
    """
    Build the full Gemini prompt with:
    - Current RAG chunks (most relevant to this question)
    - Previous RAG turns (sliding window — up to 2 historical turns)
    - Conversation history (last 20 turns)
    - Current question

    rag_history: list of chunk lists — oldest first, newest last
                 e.g. [ [turn_N-2 chunks], [turn_N-1 chunks] ]
                 The current turn's chunks are passed separately as context_chunks
    """
    rag_history = rag_history or []

    # ── Current RAG chunks ────────────────────────────────────
    current_rag_block = _format_chunks(
        context_chunks,
        "Current Clinical Context (most relevant to this question)"
    )

    # ── Previous RAG turns (oldest to newest, excluding current) ──
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

    # ── Conversation history ──────────────────────────────────
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
        f"{current_rag_block}\n\n"
        f"{prev_rag_block}"
        f"{history_block}\n"
        f"--- Current Question ---\n"
        f"Clinical Staff: {question}\n\n"
        f"Assistant:"
    )
