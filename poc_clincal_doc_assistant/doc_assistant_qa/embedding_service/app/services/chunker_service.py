from typing import List
import tiktoken


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """
    Split text into chunks of chunk_size tokens with chunk_overlap overlap.

    Uses tiktoken (cl100k_base encoding — same as GPT-4).
    Returns list of text chunk strings.

    Example:
        text     = 2000 tokens
        size     = 500
        overlap  = 50
        → chunks = [0:500], [450:950], [900:1400], [1350:1850], [1800:2000]
    """
    if not text or not text.strip():
        return []

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    chunks = []
    start  = 0

    while start < len(tokens):
        end        = min(start + chunk_size, len(tokens))
        chunk_tok  = tokens[start:end]
        chunk_text = enc.decode(chunk_tok)

        if chunk_text.strip():
            chunks.append(chunk_text.strip())

        if end == len(tokens):
            break

        start += chunk_size - chunk_overlap

    return chunks
