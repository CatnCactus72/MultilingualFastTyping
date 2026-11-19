# languages/vi_telex/composer.py
from typing import Any, Dict, Optional, Tuple
from core.composers.base import Action, KeyEvent, Passthrough, Replace
from core.conflicts.framework import ValidationIssue
from core.registry import register_composer
from languages.vi.vi_common.phonotactics import (
    is_valid_complete_syllable,
    is_valid_in_progress_state,
    parse_cells,
    render_word_state,
)
from languages.vi.vi_common.state import (
    MAX_WORD_CELLS,
    TONE_OPS,
    VOWEL_BASES,
    Cell,
    ViWordState,
)

TELEX_TONE_KEYS: Dict[str, str] = {
    "s": "TONE_SAC",
    "f": "TONE_HUYEN",
    "r": "TONE_HOI",
    "x": "TONE_NGA",
    "j": "TONE_NANG",
    "z": "TONE_CLEAR",
}

TELEX_REPEAT_MARKS: Dict[str, str] = {
    "a": "MARK_CIRC",
    "e": "MARK_CIRC",
    "o": "MARK_CIRC",
    "d": "STROKE_D",
}

WORD_BOUNDARY_CHARS = {
    " ", "\t", "\n", "\r", ".", ",", ";", ":", "!", "?",
    "(", ")", "[", "]", "{", "}", "\"", "'"
}


class ViTelexComposer:
    """Composer Tiếng Việt kiểu Telex (s/f/r/x/j/z, aa/ee/oo/dd, w)."""

    requires_preedit: bool = False

    def __init__(self, pack: Any) -> None:
        self.pack = pack
        if isinstance(pack, dict):
            self.options = dict(pack.get("options", {}))
        else:
            self.options = dict(getattr(pack, "options", {}) or {})

        self.tone_style: str = self.options.get("tone_style", "modern")
        self.validate_mode: str = self.options.get("validate", "strict")
        self.restore_invalid: bool = bool(self.options.get("restore_invalid", True))

        self.state = ViWordState()
        self.shown: str = ""
        self._last_trigger: Optional[str] = None

    def reset(self) -> None:
        self.state.clear()
        self.shown = ""
        self._last_trigger = None

    def render(self) -> str:
        return render_word_state(self.state, self.tone_style)

    def _diff_action(self, old_shown: str, new_shown: str, typed_char: str) -> Action:
        if new_shown == old_shown + typed_char:
            return Passthrough()
        common = 0
        limit = min(len(old_shown), len(new_shown))
        while common < limit and old_shown[common] == new_shown[common]:
            common += 1
        return Replace(delete_n=len(old_shown) - common, text=new_shown[common:])

    def _sync(self, typed_char: str) -> Action:
        new_shown = render_word_state(self.state, self.tone_style)
        act = self._diff_action(self.shown, new_shown, typed_char)
        self.shown = new_shown
        return act

    def backspace(self) -> Action:
        if not self.state.cells:
            self.reset()
            return Passthrough()
        old_shown = self.shown
        self.state.cells.pop()
        if self.state.raw:
            self.state.raw.pop()
        self._last_trigger = None

        if not self.state.cells:
            self.reset()
            return Passthrough()

        if not any(c.base in VOWEL_BASES for c in self.state.cells):
            self.state.tone = None

        new_shown = render_word_state(self.state, self.tone_style)
        self.shown = new_shown
        if old_shown[:-1] == new_shown:
            return Passthrough()

        common = 0
        limit = min(len(old_shown), len(new_shown))
        while common < limit and old_shown[common] == new_shown[common]:
            common += 1
        return Replace(delete_n=len(old_shown) - common, text=new_shown[common:])

    def _find_uo_indices(self, state: ViWordState) -> Optional[Tuple[int, int]]:
        parsed = parse_cells(state.cells)
        nuc = parsed.nucleus_indices
        for i in range(len(nuc) - 1):
            if state.cells[nuc[i]].base == "u" and state.cells[nuc[i + 1]].base == "o":
                return (nuc[i], nuc[i + 1])
        return None

    def _try_telex_op(self, ch: str, is_upper: bool) -> Optional[Action]:
        low = ch.lower()
        cells = self.state.cells
        if not cells:
            return None

        # 1. Nhóm lặp liền kề: aa -> â, ee -> ê, oo -> ô, dd -> đ
        if low in TELEX_REPEAT_MARKS:
            last = cells[-1]
            expected_mark = TELEX_REPEAT_MARKS[low]
            if last.base == low and not last.locked:
                if last.mark == expected_mark:
                    # Hoàn tác: aaa -> aa, ooo -> oo (khóa ô chữ lặp nhưng giữ âm tiết cho xoong/óoc)
                    last.mark = None
                    last.locked = True
                    self.state.cells.append(Cell(base=low, upper=is_upper, locked=True))
                    self.state.raw.append(ch)
                    self._last_trigger = None
                    return self._sync(ch)

                cand = self.state.clone()
                cand.cells[-1].mark = expected_mark
                if is_valid_in_progress_state(cand, self.validate_mode):
                    self.state = cand
                    self.state.raw.append(ch)
                    self.state.has_applied_op = True
                    self._last_trigger = low
                    return self._sync(ch)

        # 2. Phím 'w': ơ, ư, ươ, ă
        if low == "w":
            uo_pair = self._find_uo_indices(self.state)
            if uo_pair:
                u_idx, o_idx = uo_pair
                if cells[u_idx].mark == "MARK_HORN" or cells[o_idx].mark == "MARK_HORN":
                    if self._last_trigger == "w":
                        cells[u_idx].mark = None
                        cells[o_idx].mark = None
                        self.state.cells.append(Cell(base="w", upper=is_upper, locked=True))
                        self.state.raw.append(ch)
                        self.state.raw_mode = True
                        self._last_trigger = None
                        return self._sync(ch)
                cand = self.state.clone()
                cand.cells[u_idx].mark = "MARK_HORN"
                cand.cells[o_idx].mark = "MARK_HORN"
                if is_valid_in_progress_state(cand, self.validate_mode):
                    self.state = cand
                    self.state.raw.append(ch)
                    self.state.has_applied_op = True
                    self._last_trigger = "w"
                    return self._sync(ch)

            for i in range(len(cells) - 1, -1, -1):
                c = cells[i]
                if c.locked or c.base not in ("a", "o", "u"):
                    continue
                target_mark = "MARK_BREVE" if c.base == "a" else "MARK_HORN"
                if c.mark == target_mark and self._last_trigger == "w":
                    c.mark = None
                    self.state.cells.append(Cell(base="w", upper=is_upper, locked=True))
                    self.state.raw.append(ch)
                    self.state.raw_mode = True
                    self._last_trigger = None
                    return self._sync(ch)

                cand = self.state.clone()
                cand.cells[i].mark = target_mark
                if is_valid_in_progress_state(cand, self.validate_mode):
                    self.state = cand
                    self.state.raw.append(ch)
                    self.state.has_applied_op = True
                    self._last_trigger = "w"
                    return self._sync(ch)

        # 3. Nhóm dấu thanh: s, f, r, x, j, z
        if low in TELEX_TONE_KEYS:
            parsed = parse_cells(cells)
            if not parsed.nucleus_indices:
                return None
            op = TELEX_TONE_KEYS[low]
            if op in TONE_OPS and self.state.tone == op and self._last_trigger == low:
                self.state.tone = None
                self.state.cells.append(Cell(base=low, upper=is_upper, locked=True))
                self.state.raw.append(ch)
                self.state.raw_mode = True
                self._last_trigger = None
                return self._sync(ch)

            cand = self.state.clone()
            if op == "TONE_CLEAR":
                if cand.tone is None:
                    return None
                cand.tone = None
            else:
                cand.tone = op

            if is_valid_in_progress_state(cand, self.validate_mode):
                self.state = cand
                self.state.raw.append(ch)
                self.state.has_applied_op = True
                self._last_trigger = low
                return self._sync(ch)

        return None

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        raw_lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        if ch in WORD_BOUNDARY_CHARS:
            if (
                self.restore_invalid
                and self.state.has_applied_op
                and not self.state.raw_mode
                and not is_valid_complete_syllable(self.state, self.validate_mode)
            ):
                raw_word = "".join(self.state.raw)
                old_len = len(self.shown)
                self.reset()
                return Replace(delete_n=old_len, text=raw_word + ch)
            self.reset()
            return Passthrough()

        if len(self.state.cells) >= MAX_WORD_CELLS:
            self.reset()

        if self.state.raw_mode:
            self.state.cells.append(Cell(base=raw_lower, upper=is_upper, locked=True))
            self.state.raw.append(ch)
            return self._sync(ch)

        if self.state.cells:
            act = self._try_telex_op(ch, is_upper)
            if act is not None:
                return act

        self._last_trigger = None
        if ch.isalpha():
            self.state.cells.append(Cell(base=raw_lower, upper=is_upper))
            self.state.raw.append(ch)
            # Trường hợp gõ 'u' + 'w' -> 'ư', sau đó gõ tiếp 'o' -> tự đồng bộ thành 'ươ'
            if (
                raw_lower == "o"
                and len(self.state.cells) >= 2
                and self.state.cells[-2].base == "u"
                and self.state.cells[-2].mark == "MARK_HORN"
            ):
                cand = self.state.clone()
                cand.cells[-1].mark = "MARK_HORN"
                if is_valid_in_progress_state(cand, self.validate_mode):
                    self.state = cand
            return self._sync(ch)

        self.state.cells.append(Cell(base=raw_lower, upper=is_upper, locked=True))
        self.state.raw.append(ch)
        self.state.raw_mode = True
        return self._sync(ch)

    def settings_schema(self) -> dict:
        return {"type": "vi_telex", "options": ["tone_style", "validate", "restore_invalid"]}

    def validate_pack(self, pack: Any) -> list[ValidationIssue]:
        return []


register_composer("vi_telex", ViTelexComposer)