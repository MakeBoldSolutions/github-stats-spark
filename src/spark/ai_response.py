"""Extract usable text from AI responses that may include non-text blocks."""

from typing import Iterable


def extract_response_text(blocks: Iterable[object]) -> str:
    """Join text blocks, rejecting responses with no usable text."""
    parts = []
    for block in blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text)
    if not parts:
        raise ValueError("AI response contained no text")
    return "\n".join(parts)
