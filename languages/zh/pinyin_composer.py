from typing import Any, Dict, Optional
from core.composers.base import Action, KeyEvent, Passthrough
from core.composers.marks import BaseMarkComposer, MarkCell, SyllableBuffer
from core.registry import register_composer
from languages.zh.phonetics import (
    PINYIN_VOWELS,
    can_append_to_pinyin_syllable,
    is_valid_pinyin_syllable,
    select_pinyin_tone_index,
)

DEFAULT_PINYIN_MAP: Dict[str, str] = {
    "1": "TONE_1",
    "2": "TONE_2",
    "3": "TONE_3",
    "4": "TONE_4",
    "0": "TONE_CLEAR",
    ":": "MARK_DIAERESIS",
}

TONE_OPS = {"TONE_1", "TONE_2", "TONE_3", "TONE_4", "TONE_CLEAR"}


class PinyinMarkComposer(BaseMarkComposer):
    """Composer Cơ chế B cho Pinyin dấu thanh (nǚ, cōngmíng), kế thừa BaseMarkComposer."""

    VOWEL_BASES = PINYIN_VOWELS

    MARK_COMBINING = {
        "MARK_DIAERESIS": "\u0308",
    }
    TONE_COMBINING = {
        "TONE_1": "\u0304",  # ā, ē, ī, ō, ū, ǖ
        "TONE_2": "\u0301",  # á, é, í, ó, ú, ǘ
        "TONE_3": "\u030c",  # ǎ, ě, ǐ, ǒ, ǔ, ǚ
        "TONE_4": "\u0300",  # à, è, ì, ò, ù, ǜ
    }

    def __init__(self, pack: Any) -> None:
        super().__init__(pack)
        self.v_as_umlaut: bool = bool(self.options.get("v_as_umlaut", True))
        self.key_to_op: Dict[str, str] = self._build_key_map()
        self._last_tone_key: Optional[str] = None

    def _build_key_map(self) -> Dict[str, str]:
        bindings = (
            self.pack.get("bindings")
            if isinstance(self.pack, dict)
            else getattr(self.pack, "bindings", None)
        )
        if isinstance(bindings, dict):
            return {str(v).lower(): k for k, v in bindings.items() if v}
        return dict(DEFAULT_PINYIN_MAP)

    def reset(self) -> None:
        super().reset()
        self._last_tone_key = None

    def select_tone_index(self, syllable: SyllableBuffer) -> Optional[int]:
        return select_pinyin_tone_index(syllable)

    def validate_syllable(
        self, syllable: SyllableBuffer, is_complete: bool = False
    ) -> bool:
        if self.validate_mode == "off":
            return True
        return is_valid_pinyin_syllable(
            syllable,
            strict=(self.validate_mode == "strict"),
            require_complete=is_complete,
        )

    def _apply_diaeresis(self, syl: SyllableBuffer) -> bool:
        for i in range(len(syl.cells) - 1, -1, -1):
            c = syl.cells[i]
            if c.base == "u" and not c.locked:
                if c.mark == "MARK_DIAERESIS":
                    return False
                c.mark = "MARK_DIAERESIS"
                return True
        return False

    def _insert_letter(self, ch: str, lower: str, is_upper: bool) -> Action:
        # Dấu nháy ' tách âm tiết rõ ràng (ví dụ xi'an)
        if ch == "'":
            if self.state.active_syllable.cells:
                self.state.active_syllable.locked_final = True
                self.state.syllables.append(SyllableBuffer())
            self.state.raw.append(ch)
            self._last_tone_key = None
            return Passthrough()

        # Phím 'v' dùng làm 'ü' (base='u', mark='MARK_DIAERESIS') nếu bật tùy chọn
        if lower == "v" and self.v_as_umlaut:
            target_base = "u"
            target_mark: Optional[str] = "MARK_DIAERESIS"
        else:
            target_base = lower
            target_mark = None

        syl = self.state.active_syllable
        probe_cell = MarkCell(base=target_base, upper=is_upper, mark=target_mark)
        probe_syl = syl.clone()
        probe_syl.cells.append(probe_cell)

        if (
            self.validate_mode == "strict"
            and syl.cells
            and not can_append_to_pinyin_syllable(syl, "ü" if target_mark else target_base)
        ):
            # Chốt âm tiết hiện tại và mở âm tiết con mới trong cùng từ viết liền (cōngmíng)
            syl.locked_final = True
            new_syl = SyllableBuffer(cells=[probe_cell])
            self.state.syllables.append(new_syl)
        else:
            syl.cells.append(probe_cell)

        self.state.raw.append(ch)
        self._last_tone_key = None
        return self._sync(ch)

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        if ch in self.boundary_chars and ch != "'":
            self._last_tone_key = None
            return self._on_boundary(ch)

        if self.state.total_cells >= self.max_cells:
            self.reset()
            return Passthrough()

        syl = self.state.active_syllable
        op = self.key_to_op.get(lower)

        # Xử lý phím dấu thanh (1..4, 0) hoặc dấu hai chấm (:)
        if op and not self.state.raw_mode and syl.cells:
            if op in TONE_OPS:
                has_vowel = any(c.base in self.VOWEL_BASES for c in syl.cells)
                if has_vowel:
                    new_tone = None if op == "TONE_CLEAR" else op
                    # Gõ lặp cùng phím thanh điệu -> hoàn tác thanh
                    if syl.tone == new_tone and self._last_tone_key == lower:
                        syl.tone = None
                        syl.cells.append(MarkCell(base=lower, upper=is_upper, locked=True))
                        self.state.raw.append(ch)
                        self.state.raw_mode = True
                        self._last_tone_key = None
                        return self._sync(ch)

                    cand = syl.clone()
                    cand.tone = new_tone
                    if self.validate_syllable(cand):
                        self.state.syllables[-1] = cand
                        self.state.raw.append(ch)
                        self.state.has_applied_op = True
                        self._last_tone_key = lower
                        return self._sync(ch)

            elif op == "MARK_DIAERESIS":
                cand = syl.clone()
                if self._apply_diaeresis(cand) and self.validate_syllable(cand):
                    self.state.syllables[-1] = cand
                    self.state.raw.append(ch)
                    self.state.has_applied_op = True
                    self._last_tone_key = None
                    return self._sync(ch)

        if ch.isalpha() or ch == "'":
            return self._insert_letter(ch, lower, is_upper)

        # Ký tự khác không áp dụng được -> literal + raw_mode
        syl.cells.append(MarkCell(base=lower, upper=is_upper, locked=True))
        self.state.raw.append(ch)
        self.state.raw_mode = True
        self._last_tone_key = None
        return self._sync(ch)


register_composer("zh_pinyin", PinyinMarkComposer)