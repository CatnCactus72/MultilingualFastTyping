# core/layers/unicode_utils.py
import unicodedata
from typing import Optional


def normalize_text(text: str, form: Optional[str] = "NFC") -> str:
    if not form or form.upper() == "NONE":
        return text
    return unicodedata.normalize(form.upper(), text)


def codepoint_len(text: str) -> int:
    return len(text)