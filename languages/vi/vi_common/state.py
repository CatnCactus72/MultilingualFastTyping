# languages/vi/state.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import unicodedata

# 10 phép toán cố định (Phụ lục A.1)
TONE_OPS: Tuple[str, ...] = (
    "TONE_SAC",
    "TONE_HUYEN",
    "TONE_HOI",
    "TONE_NGA",
    "TONE_NANG",
)
ALL_VI_OPS: Tuple[str, ...] = TONE_OPS + (
    "TONE_CLEAR",
    "MARK_CIRC",
    "MARK_HORN",
    "MARK_BREVE",
    "STROKE_D",
)

VOWEL_BASES: Set[str] = {"a", "e", "i", "o", "u", "y"}

# Tập chữ gốc đích cho từng phép toán (dùng cho C-VI-01 & C-VI-03)
OP_TARGETS: Dict[str, Set[str]] = {
    "TONE_SAC": set(VOWEL_BASES),
    "TONE_HUYEN": set(VOWEL_BASES),
    "TONE_HOI": set(VOWEL_BASES),
    "TONE_NGA": set(VOWEL_BASES),
    "TONE_NANG": set(VOWEL_BASES),
    "TONE_CLEAR": set(VOWEL_BASES),
    "MARK_CIRC": {"a", "e", "o"},
    "MARK_HORN": {"o", "u"},
    "MARK_BREVE": {"a"},
    "STROKE_D": {"d"},
}

MARK_COMBINING: Dict[str, str] = {
    "MARK_CIRC": "\u0302",   # ^
    "MARK_HORN": "\u031b",   # ơ, ư
    "MARK_BREVE": "\u0306",  # ă
}

TONE_COMBINING: Dict[str, str] = {
    "TONE_SAC": "\u0301",
    "TONE_HUYEN": "\u0300",
    "TONE_HOI": "\u0309",
    "TONE_NGA": "\u0303",
    "TONE_NANG": "\u0323",
}

MAX_WORD_CELLS = 24


def compose_cell_char(
    base: str,
    upper: bool,
    mark: Optional[str] = None,
    tone: Optional[str] = None,
) -> str:
    """Ghép 1 ô (base, upper, mark, tone) thành đúng 1 ký tự NFC dựng sẵn."""
    b = base.lower()
    if b == "d" and mark == "STROKE_D":
        ch = "Đ" if upper else "đ"
        return ch

    s = b.upper() if upper else b
    if mark in MARK_COMBINING:
        s += MARK_COMBINING[mark]
    if tone in TONE_COMBINING:
        s += TONE_COMBINING[tone]
    return unicodedata.normalize("NFC", s)


def decompose_vietnamese_char(ch: str) -> Tuple[str, bool, Optional[str], Optional[str]]:
    """Phân rã 1 ký tự tiếng Việt NFC thành (base_lower, is_upper, mark, tone)."""
    is_up = ch.isupper()
    low = ch.lower()
    if low == "đ":
        return ("d", is_up, "STROKE_D", None)

    nfd = unicodedata.normalize("NFD", low)
    base = nfd[0]
    mark: Optional[str] = None
    tone: Optional[str] = None
    for comb in nfd[1:]:
        for m_name, m_char in MARK_COMBINING.items():
            if comb == m_char:
                mark = m_name
        for t_name, t_char in TONE_COMBINING.items():
            if comb == t_char:
                tone = t_name
    return (base, is_up, mark, tone)


@dataclass
class Cell:
    base: str                  # Chữ cái gốc in thường ('a'..'z')
    upper: bool = False
    mark: Optional[str] = None  # None | MARK_CIRC | MARK_HORN | MARK_BREVE | STROKE_D
    locked: bool = False

    def clone(self) -> "Cell":
        return Cell(self.base, self.upper, self.mark, self.locked)

    def marked_lower(self) -> str:
        """Trả về ký tự thường có dấu chữ (chưa có dấu thanh), ví dụ 'ă', 'ê', 'đ'."""
        return compose_cell_char(self.base, False, self.mark, None)


@dataclass
class ViWordState:
    cells: List[Cell] = field(default_factory=list)
    tone: Optional[str] = None
    raw: List[str] = field(default_factory=list)
    raw_mode: bool = False
    has_applied_op: bool = False

    def clone(self) -> "ViWordState":
        return ViWordState(
            cells=[c.clone() for c in self.cells],
            tone=self.tone,
            raw=list(self.raw),
            raw_mode=self.raw_mode,
            has_applied_op=self.has_applied_op,
        )

    def clear(self) -> None:
        self.cells.clear()
        self.tone = None
        self.raw.clear()
        self.raw_mode = False
        self.has_applied_op = False