# languages/vi/vi_telex/composer.py
from typing import Any, Dict, Optional
from core.composers.base import Action, KeyEvent, Passthrough
from core.composers.marks import BaseMarkComposer, MarkCell, SyllableBuffer
from core.registry import register_composer
from languages.vi.vi_common.phonotactics import (
    is_valid_in_progress_cells,
    select_vi_tone_index,
    render_vi_cells,
)

DEFAULT_TELEX_TONES: Dict[str, str] = {
    "s": "TONE_SAC",
    "f": "TONE_HUYEN",
    "r": "TONE_HOI",
    "x": "TONE_NGA",
    "j": "TONE_NANG",
    "z": "TONE_CLEAR",
}

class ViTelexComposer(BaseMarkComposer):
    """Bộ gõ Tiếng Việt kiểu Telex kế thừa khung chung BaseMarkComposer."""

    MARK_COMBINING = {
        "MARK_CIRC": "\u0302",
        "MARK_HORN": "\u031b",
        "MARK_BREVE": "\u0306",
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
        self.tone_keys: Dict[str, str] = dict(DEFAULT_TELEX_TONES)
        self._last_telex_op: Optional[str] = None

    def reset(self) -> None:
        super().reset()
        self._last_telex_op = None

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

    def _try_telex_mark(self, syl: SyllableBuffer, lower: str) -> Optional[str]:
        """Thử biến đổi mũ/móc/trăng/đ theo quy tắc Telex trên bản sao `syl`."""
        # 1. Lặp phụ âm đầu 'dd' -> 'đ'
        if lower == "d":
            for i in range(len(syl.cells) - 1, -1, -1):
                c = syl.cells[i]
                if c.base == "d" and not c.locked:
                    if c.mark == "STROKE_D":
                        return None
                    c.mark = "STROKE_D"
                    return "STROKE_D"
            return None

        # 2. Lặp nguyên âm 'aa', 'ee', 'oo' -> 'â', 'ê', 'ô'
        if lower in {"a", "e", "o"}:
            for i in range(len(syl.cells) - 1, -1, -1):
                c = syl.cells[i]
                if c.base == lower and not c.locked:
                    if c.mark == "MARK_CIRC":
                        return None
                    c.mark = "MARK_CIRC"
                    return "MARK_CIRC"
            return None

        # 3. Phím 'w' -> 'ă', 'ơ', 'ư' (ưu tiên cặp 'uo' -> 'ươ')
        if lower == "w":
            if len(syl.cells) >= 2:
                for i in range(len(syl.cells) - 2, -1, -1):
                    c1, c2 = syl.cells[i], syl.cells[i + 1]
                    if (
                        c1.base == "u"
                        and c2.base == "o"
                        and not c1.locked
                        and not c2.locked
                    ):
                        if c1.mark == "MARK_HORN" and c2.mark == "MARK_HORN":
                            return None
                        c1.mark = "MARK_HORN"
                        c2.mark = "MARK_HORN"
                        return "MARK_HORN"

            for i in range(len(syl.cells) - 1, -1, -1):
                c = syl.cells[i]
                if c.base in {"a", "o", "u"} and not c.locked:
                    target_mark = "MARK_BREVE" if c.base == "a" else "MARK_HORN"
                    if c.mark == target_mark:
                        return None
                    c.mark = target_mark
                    return target_mark
        return None

    def _undo_telex(self, syl: SyllableBuffer, ch: str, is_upper: bool) -> Action:
        """Gõ lặp phím dấu Telex -> hoàn tác về chữ thường + khóa ô (ví dụ ooo -> oo cho xoong)."""
        op = self._last_telex_op
        if op and op.startswith("TONE_"):
            syl.tone = None
            for c in syl.cells:
                if c.base in self.VOWEL_BASES:
                    c.locked = True
            self.state.raw_mode = True
        elif op == "STROKE_D":
            for i in range(len(syl.cells) - 1, -1, -1):
                if syl.cells[i].base == "d" and syl.cells[i].mark == "STROKE_D":
                    syl.cells[i].mark = None
                    syl.cells[i].locked = True
                    break
        elif op:
            for i in range(len(syl.cells) - 1, -1, -1):
                if syl.cells[i].mark == op:
                    syl.cells[i].mark = None
                    syl.cells[i].locked = True
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
        self._last_telex_op = None
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

        if ch.isalpha() and not self.state.raw_mode and syl.cells:
            # 1. Hoàn tác nếu lặp phím dấu ngay sau khi biến đổi (aa->â, aaa->aa; ooo->oo)
            if (
                self._last_telex_op is not None
                and self.state.raw
                and self.state.raw[-1].lower() == lower
            ):
                return self._undo_telex(syl, ch, is_upper)

            # 2. Thử dấu thanh Telex (s, f, r, x, j, z)
            if lower in self.tone_keys:
                tone_op = self.tone_keys[lower]
                new_tone = None if tone_op == "TONE_CLEAR" else tone_op
                if syl.tone != new_tone and any(
                    c.base in self.VOWEL_BASES for c in syl.cells
                ):
                    cand = syl.clone()
                    cand.tone = new_tone
                    if self.validate_syllable(cand):
                        self.state.syllables[-1] = cand
                        self.state.raw.append(ch)
                        self.state.has_applied_op = True
                        self._last_telex_op = tone_op
                        return self._sync(ch)

            # 3. Thử dấu chữ Telex (aa, ee, oo, dd, w)
            if lower in {"a", "e", "o", "d", "w"}:
                cand = syl.clone()
                applied = self._try_telex_mark(cand, lower)
                if applied and self.validate_syllable(cand):
                    self.state.syllables[-1] = cand
                    self.state.raw.append(ch)
                    self.state.has_applied_op = True
                    self._last_telex_op = applied
                    return self._sync(ch)

        # Chèn chữ cái thường (tự đồng bộ 'ư' + 'o' -> 'ươ')
        if ch.isalpha():
            mark: Optional[str] = None
            if lower == "o" and syl.cells:
                prev = syl.cells[-1]
                if prev.base == "u" and prev.mark == "MARK_HORN" and not prev.locked:
                    mark = "MARK_HORN"
            syl.cells.append(MarkCell(base=lower, upper=is_upper, mark=mark))
            self.state.raw.append(ch)
            self._last_telex_op = None
            return self._sync(ch)

        # Ký tự số / ký hiệu không phải dấu -> bật raw_mode
        syl.cells.append(MarkCell(base=lower, upper=is_upper, locked=True))
        self.state.raw.append(ch)
        self.state.raw_mode = True
        self._last_telex_op = None
        return self._sync(ch)
    
    def render_syllable(self, syllable: SyllableBuffer) -> str:
        return render_vi_cells(syllable.cells, syllable.tone, self.tone_style)


register_composer("vi_telex", ViTelexComposer)