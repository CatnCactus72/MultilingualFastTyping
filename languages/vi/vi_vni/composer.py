# languages/vi/vi_vni/composer.py
from typing import Any, Dict, List, Optional
from core.composers.base import Action, KeyEvent, Passthrough
from core.composers.marks import BaseMarkComposer, MarkCell, SyllableBuffer
from core.registry import register_composer
from languages.vi.vi_common.phonotactics import (
    is_valid_in_progress_cells,
    select_vi_tone_index,
    render_vi_cells,
)

DEFAULT_VNI_MAP: Dict[str, str] = {
    "1": "TONE_SAC",
    "2": "TONE_HUYEN",
    "3": "TONE_HOI",
    "4": "TONE_NGA",
    "5": "TONE_NANG",
    "0": "TONE_CLEAR",
    "6": "MARK_CIRC",
    "7": "MARK_HORN",
    "8": "MARK_BREVE",
    "9": "STROKE_D",
}

TONE_OPS = {"TONE_SAC", "TONE_HUYEN", "TONE_HOI", "TONE_NGA", "TONE_NANG", "TONE_CLEAR"}


class ViVniComposer(BaseMarkComposer):
    """Bộ gõ Tiếng Việt kiểu VNI kế thừa khung chung BaseMarkComposer."""

    MARK_COMBINING = {
        "MARK_CIRC": "\u0302",   # ^
        "MARK_HORN": "\u031b",   # ơ, ư
        "MARK_BREVE": "\u0306",  # ă
    }
    TONE_COMBINING = {
        "TONE_SAC": "\u0301",
        "TONE_HUYEN": "\u0300",
        "TONE_HOI": "\u0309",
        "TONE_NGA": "\u0303",
        "TONE_NANG": "\u0323",
    }
    SPECIAL_CHARS = {
        ("d", "STROKE_D"): "đ",
    }

    def __init__(self, pack: Any) -> None:
        super().__init__(pack)
        self.tone_style: str = self.options.get("tone_style", "modern")
        self.key_to_op: Dict[str, str] = self._build_key_map()
        self._last_vni_key: Optional[str] = None

    def _build_key_map(self) -> Dict[str, str]:
        bindings = (
            self.pack.get("bindings")
            if isinstance(self.pack, dict)
            else getattr(self.pack, "bindings", None)
        )
        if isinstance(bindings, dict):
            return {str(v).lower(): k for k, v in bindings.items() if v}
        return dict(DEFAULT_VNI_MAP)

    def reset(self) -> None:
        super().reset()
        self._last_vni_key = None

    def select_tone_index(self, syllable: SyllableBuffer) -> Optional[int]:
        return select_vi_tone_index(syllable.cells, self.tone_style)

    def validate_syllable(
        self, syllable: SyllableBuffer, is_complete: bool = False
    ) -> bool:
        if self.validate_mode == "off":
            return True
        return is_valid_in_progress_cells(
            syllable.cells,
            syllable.tone,
            strict=(self.validate_mode == "strict"),
            require_complete=is_complete,
        )

    def _insert_char(self, ch: str, is_upper: bool) -> Action:
        syl = self.state.active_syllable
        lower = ch.lower()
        mark: Optional[str] = None

        # Tự động đồng bộ ươ khi gõ 'ư' rồi gõ tiếp 'o' (ví dụ t-u-7-o-n-g -> tương)
        if lower == "o" and syl.cells:
            prev = syl.cells[-1]
            if prev.base == "u" and prev.mark == "MARK_HORN" and not prev.locked:
                mark = "MARK_HORN"

        syl.cells.append(MarkCell(base=lower, upper=is_upper, mark=mark))
        self.state.raw.append(ch)
        self._last_vni_key = None
        return self._sync(ch)

    def _apply_op_to_syllable(self, syl: SyllableBuffer, op: str) -> bool:
        """Áp dụng thử phép toán VNI lên bản sao âm tiết. Trả True nếu thay đổi trạng thái."""
        if op in TONE_OPS:
            has_vowel = any(c.base in self.VOWEL_BASES for c in syl.cells)
            if not has_vowel:
                return False
            new_tone = None if op == "TONE_CLEAR" else op
            if syl.tone == new_tone:
                return False
            syl.tone = new_tone
            return True

        if op == "STROKE_D":
            for i in range(len(syl.cells) - 1, -1, -1):
                c = syl.cells[i]
                if c.base == "d" and not c.locked:
                    if c.mark == "STROKE_D":
                        return False
                    c.mark = "STROKE_D"
                    return True
            return False

        # MARK_CIRC (6), MARK_HORN (7), MARK_BREVE (8)
        targets = {
            "MARK_CIRC": {"a", "e", "o"},
            "MARK_HORN": {"o", "u"},
            "MARK_BREVE": {"a"},
        }.get(op, set())

        # Ngoại lệ cặp 'uo' + '7' -> gắn đồng thời MARK_HORN cho cả hai (ươ)
        if op == "MARK_HORN" and len(syl.cells) >= 2:
            for i in range(len(syl.cells) - 2, -1, -1):
                c1, c2 = syl.cells[i], syl.cells[i + 1]
                if (
                    c1.base == "u"
                    and c2.base == "o"
                    and not c1.locked
                    and not c2.locked
                ):
                    if c1.mark == "MARK_HORN" and c2.mark == "MARK_HORN":
                        return False
                    c1.mark = "MARK_HORN"
                    c2.mark = "MARK_HORN"
                    return True

        for i in range(len(syl.cells) - 1, -1, -1):
            c = syl.cells[i]
            if c.base in targets and not c.locked:
                if c.mark == op:
                    return False
                c.mark = op
                return True
        return False

    def _undo_op(self, syl: SyllableBuffer, op: str, ch: str, is_upper: bool) -> Action:
        """Gõ lặp cùng phím số VNI -> gỡ dấu, khóa ô và chèn phím số thô."""
        if op in TONE_OPS:
            syl.tone = None
            for c in syl.cells:
                if c.base in self.VOWEL_BASES:
                    c.locked = True
        elif op == "STROKE_D":
            for i in range(len(syl.cells) - 1, -1, -1):
                if syl.cells[i].base == "d" and syl.cells[i].mark == "STROKE_D":
                    syl.cells[i].mark = None
                    syl.cells[i].locked = True
                    break
        else:
            for i in range(len(syl.cells) - 1, -1, -1):
                if syl.cells[i].mark == op:
                    syl.cells[i].mark = None
                    syl.cells[i].locked = True
                    # Nếu đang là cặp 'ươ', gỡ cả hai
                    if (
                        op == "MARK_HORN"
                        and i > 0
                        and syl.cells[i - 1].base == "u"
                        and syl.cells[i - 1].mark == "MARK_HORN"
                    ):
                        syl.cells[i - 1].mark = None
                        syl.cells[i - 1].locked = True
                    break

        syl.cells.append(MarkCell(base=ch.lower(), upper=is_upper, locked=True))
        self.state.raw.append(ch)
        self.state.raw_mode = True
        self._last_vni_key = None
        return self._sync(ch)

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        if ch in self.boundary_chars:
            return self._on_boundary(ch)

        if self.state.total_cells >= self.max_cells:
            self.reset()
            return Passthrough()

        syl = self.state.active_syllable
        op = self.key_to_op.get(lower)

        # Kiểm tra phím dấu VNI khi chưa bật raw_mode
        if op and not self.state.raw_mode and syl.cells:
            # 1. Kiểm tra hoàn tác khi nhấn lặp phím VNI liền trước
            if self._last_vni_key == lower:
                return self._undo_op(syl, op, ch, is_upper)

            # 2. Thử áp dụng dấu trên bản sao âm tiết và kiểm tra chính tả
            cand = syl.clone()
            if self._apply_op_to_syllable(cand, op) and self.validate_syllable(cand):
                self.state.syllables[-1] = cand
                self.state.raw.append(ch)
                self.state.has_applied_op = True
                self._last_vni_key = lower
                return self._sync(ch)

        # Phím chữ cái thông thường
        if ch.isalpha():
            return self._insert_char(ch, is_upper)

        # Số không phải dấu hoặc bị từ chối chính tả -> bật raw_mode
        syl.cells.append(MarkCell(base=lower, upper=is_upper, locked=True))
        self.state.raw.append(ch)
        self.state.raw_mode = True
        self._last_vni_key = None
        return self._sync(ch)

    def render_syllable(self, syllable: SyllableBuffer) -> str:
        return render_vi_cells(syllable.cells, syllable.tone, self.tone_style)

register_composer("vi_vni", ViVniComposer)