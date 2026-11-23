# core/composers/marks.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import unicodedata
from core.composers.base import Action, KeyEvent, Passthrough, Replace

DEFAULT_MAX_CELLS = 32
DEFAULT_BOUNDARIES = {
    " ", "\t", "\n", "\r", ".", ",", ";", ":", "!", "?",
    "(", ")", "[", "]", "{", "}", "\"", "'"
}


@dataclass
class MarkCell:
    """Một ô ký tự cơ sở kèm dấu chữ phụ (ví dụ ^, ơ/ư, ă, đ, ü)."""
    base: str                   # Chữ cái gốc in thường ('a'..'z')
    upper: bool = False
    mark: Optional[str] = None  # Tên dấu chữ phụ (ví dụ MARK_CIRC, MARK_DIAERESIS...)
    locked: bool = False        # Khóa ô sau khi hoàn tác để không tự biến đổi lại

    def clone(self) -> "MarkCell":
        return MarkCell(self.base, self.upper, self.mark, self.locked)


@dataclass
class SyllableBuffer:
    """Bộ đệm của 1 âm tiết (tiếng Việt có 1 âm tiết/từ; Pinyin có thể nhiều âm tiết viết liền)."""
    cells: List[MarkCell] = field(default_factory=list)
    tone: Optional[str] = None
    locked_final: bool = False  # Đã chốt khi chuyển sang âm tiết kế tiếp trong từ viết liền

    def clone(self) -> "SyllableBuffer":
        return SyllableBuffer(
            cells=[c.clone() for c in self.cells],
            tone=self.tone,
            locked_final=self.locked_final,
        )


@dataclass
class MarkWordState:
    """Trạng thái toàn bộ từ đang gõ (hỗ trợ 1 hoặc nhiều âm tiết viết liền)."""
    syllables: List[SyllableBuffer] = field(default_factory=lambda: [SyllableBuffer()])
    raw: List[str] = field(default_factory=list)
    raw_mode: bool = False
    has_applied_op: bool = False

    @property
    def active_syllable(self) -> SyllableBuffer:
        if not self.syllables:
            self.syllables.append(SyllableBuffer())
        return self.syllables[-1]

    @property
    def total_cells(self) -> int:
        return sum(len(s.cells) for s in self.syllables)

    def clone(self) -> "MarkWordState":
        return MarkWordState(
            syllables=[s.clone() for s in self.syllables],
            raw=list(self.raw),
            raw_mode=self.raw_mode,
            has_applied_op=self.has_applied_op,
        )

    def clear(self) -> None:
        self.syllables = [SyllableBuffer()]
        self.raw.clear()
        self.raw_mode = False
        self.has_applied_op = False


def compose_nfc_char(
    base: str,
    upper: bool,
    mark_combining: Optional[str] = None,
    tone_combining: Optional[str] = None,
    special_map: Optional[Dict[Tuple[str, Optional[str]], str]] = None,
    mark_name: Optional[str] = None,
) -> str:
    """Ghép 1 ô thành đúng 1 code point Unicode chuẩn NFC."""
    b = base.lower()
    if special_map and (b, mark_name) in special_map:
        ch = special_map[(b, mark_name)]
        if tone_combining:
            ch = unicodedata.normalize("NFC", ch + tone_combining)
        return ch.upper() if upper else ch

    s = b.upper() if upper else b
    if mark_combining:
        s += mark_combining
    if tone_combining:
        s += tone_combining
    return unicodedata.normalize("NFC", s)


class BaseMarkComposer:
    """
    Khung xử lý chung cho Cơ chế B (Tiếng Việt, Pinyin dấu thanh, Yoruba, Navajo).
    Quản lý vòng đời bộ đệm, hoàn tác, raw_mode, backspace và đồng bộ màn hình.
    """

    requires_preedit: bool = False
    max_cells: int = DEFAULT_MAX_CELLS
    boundary_chars = DEFAULT_BOUNDARIES

    # Bảng ánh xạ tên dấu -> ký tự Unicode combining (lớp con ghi đè)
    MARK_COMBINING: Dict[str, str] = {}
    TONE_COMBINING: Dict[str, str] = {}
    SPECIAL_CHARS: Dict[Tuple[str, Optional[str]], str] = {}
    VOWEL_BASES = {"a", "e", "i", "o", "u", "y"}

    def __init__(self, pack: object) -> None:
        self.pack = pack
        if isinstance(pack, dict):
            self.options = dict(pack.get("options", {}))
        else:
            self.options = dict(getattr(pack, "options", {}) or {})

        self.validate_mode: str = self.options.get("validate", "strict")
        self.restore_invalid: bool = bool(self.options.get("restore_invalid", True))

        self.state = MarkWordState()
        self.shown: str = ""

    # --- Các Hook ngữ âm để lớp con (Tiếng Việt / Pinyin) cài đặt ---

    def should_split_syllable(
        self, current: SyllableBuffer, ch: str, is_upper: bool
    ) -> bool:
        """Trả True nếu ký tự mới bắt đầu âm tiết kế tiếp trong từ viết liền (Pinyin)."""
        return False

    def select_tone_index(self, syllable: SyllableBuffer) -> Optional[int]:
        """Trả về chỉ số ô trong `syllable.cells` nhận dấu thanh."""
        for i, c in enumerate(syllable.cells):
            if c.base in self.VOWEL_BASES:
                return i
        return None

    def validate_syllable(
        self, syllable: SyllableBuffer, is_complete: bool = False
    ) -> bool:
        """Kiểm tra âm tiết hợp lệ (đang gõ dở hoặc hoàn chỉnh)."""
        return True

    def render_syllable(self, syllable: SyllableBuffer) -> str:
        """Kết xuất 1 âm tiết sang chuỗi Unicode NFC."""
        tone_idx = self.select_tone_index(syllable) if syllable.tone else None
        tone_comb = self.TONE_COMBINING.get(syllable.tone or "")
        out: List[str] = []
        for i, cell in enumerate(syllable.cells):
            mark_comb = self.MARK_COMBINING.get(cell.mark or "")
            t_comb = tone_comb if i == tone_idx else None
            out.append(
                compose_nfc_char(
                    cell.base,
                    cell.upper,
                    mark_combining=mark_comb,
                    tone_combining=t_comb,
                    special_map=self.SPECIAL_CHARS,
                    mark_name=cell.mark,
                )
            )
        return "".join(out)

    # --- Các phương thức lõi dùng chung ---

    def reset(self) -> None:
        self.state.clear()
        self.shown = ""

    def render(self) -> str:
        return "".join(self.render_syllable(s) for s in self.state.syllables)

    def _diff_action(self, old_shown: str, new_shown: str, typed_char: str) -> Action:
        """So tiền tố chung để trả Passthrough hoặc Replace(delete_n, text)."""
        if new_shown == old_shown + typed_char:
            return Passthrough()
        common = 0
        limit = min(len(old_shown), len(new_shown))
        while common < limit and old_shown[common] == new_shown[common]:
            common += 1
        return Replace(delete_n=len(old_shown) - common, text=new_shown[common:])

    def _sync(self, typed_char: str) -> Action:
        new_shown = self.render()
        act = self._diff_action(self.shown, new_shown, typed_char)
        self.shown = new_shown
        return act

    def backspace(self) -> Action:
        """Xóa 1 ký tự cuối, tự lùi về âm tiết trước nếu viết liền và tính lại vị trí dấu thanh."""
        if self.state.total_cells == 0:
            self.reset()
            return Passthrough()

        old_shown = self.shown
        syl = self.state.active_syllable
        while not syl.cells and len(self.state.syllables) > 1:
            self.state.syllables.pop()
            syl = self.state.active_syllable
            syl.locked_final = False

        if syl.cells:
            syl.cells.pop()
        if self.state.raw:
            self.state.raw.pop()

        if not syl.cells and len(self.state.syllables) > 1:
            self.state.syllables.pop()
            self.state.active_syllable.locked_final = False
        elif not syl.cells:
            self.reset()
            return Passthrough()
        elif not any(c.base in self.VOWEL_BASES for c in syl.cells):
            syl.tone = None

        new_shown = self.render()
        self.shown = new_shown
        if old_shown[:-1] == new_shown:
            return Passthrough()

        common = 0
        limit = min(len(old_shown), len(new_shown))
        while common < limit and old_shown[common] == new_shown[common]:
            common += 1
        return Replace(delete_n=len(old_shown) - common, text=new_shown[common:])

    def _on_boundary(self, boundary_char: str) -> Action:
        """Khôi phục chuỗi phím thô nếu từ biến đổi không hợp lệ khi kết thúc từ."""
        if (
            self.restore_invalid
            and self.state.has_applied_op
            and not self.state.raw_mode
            and any(
                not self.validate_syllable(s, is_complete=True)
                for s in self.state.syllables
                if s.cells
            )
        ):
            raw_word = "".join(self.state.raw)
            old_len = len(self.shown)
            self.reset()
            return Replace(delete_n=old_len, text=raw_word + boundary_char)

        self.reset()
        return Passthrough()

    def settings_schema(self) -> dict:
        return {"type": "marks", "options": ["validate", "restore_invalid"]}

    def validate_pack(self, pack: object) -> list:
        return []