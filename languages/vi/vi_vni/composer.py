# languages/vi_vni/composer.py
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
    OP_TARGETS,
    TONE_OPS,
    VOWEL_BASES,
    Cell,
    ViWordState,
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

WORD_BOUNDARY_CHARS = {
    " ", "\t", "\n", "\r", ".", ",", ";", ":", "!", "?",
    "(", ")", "[", "]", "{", "}", "\"", "'"
}


class ViVniComposer:
    """Composer Tiếng Việt kiểu VNI (1..5 thanh, 6..8 mũ/móc/trăng, 9 đ, 0 xóa thanh)."""

    requires_preedit: bool = False

    def __init__(self, pack: Any) -> None:
        self.pack = pack
        if isinstance(pack, dict):
            self.options = dict(pack.get("options", {}))
            raw_bind = pack.get("bindings") or DEFAULT_VNI_MAP
        else:
            self.options = dict(getattr(pack, "options", {}) or {})
            raw_bind = getattr(pack, "bindings", None) or DEFAULT_VNI_MAP

        self.tone_style: str = self.options.get("tone_style", "modern")
        self.validate_mode: str = self.options.get("validate", "strict")
        self.restore_invalid: bool = bool(self.options.get("restore_invalid", True))

        # Hỗ trợ định dạng {op: key} hoặc {key: op}
        self.key_to_op: Dict[str, str] = {}
        if isinstance(raw_bind, dict):
            for k, v in raw_bind.items():
                if k in OP_TARGETS:
                    self.key_to_op[str(v).lower()] = k
                else:
                    self.key_to_op[str(k).lower()] = v
        if not self.key_to_op:
            self.key_to_op = dict(DEFAULT_VNI_MAP)

        self.state = ViWordState()
        self.shown: str = ""
        self._last_key: Optional[str] = None

    def reset(self) -> None:
        self.state.clear()
        self.shown = ""
        self._last_key = None

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
        self._last_key = None

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

    def _apply_vni_key(self, ch: str, is_upper: bool) -> Optional[Action]:
        op = self.key_to_op.get(ch.lower())
        if not op or not self.state.cells:
            return None

        cells = self.state.cells
        if op in TONE_OPS or op == "TONE_CLEAR":
            parsed = parse_cells(cells)
            if not parsed.nucleus_indices:
                return None
            target_indices = [parsed.nucleus_indices[-1]]
        else:
            target_indices = [
                i for i in range(len(cells) - 1, -1, -1)
                if cells[i].base in OP_TARGETS[op] and not cells[i].locked
            ]
            if not target_indices:
                return None

        for idx in target_indices:
            target_cell = cells[idx]
            is_same_tone = op in TONE_OPS and self.state.tone == op and self._last_key == ch.lower()
            is_same_mark = op in ("MARK_CIRC", "MARK_HORN", "MARK_BREVE", "STROKE_D") and (
                target_cell.mark == op and self._last_key == ch.lower()
            )

            # Hoàn tác khi gõ lặp phím VNI (ví dụ a66 -> a6, a11 -> a1)
            if is_same_tone or is_same_mark:
                if is_same_tone:
                    self.state.tone = None
                else:
                    uo_pair = self._find_uo_indices(self.state)
                    if op == "MARK_HORN" and uo_pair and idx in uo_pair:
                        self.state.cells[uo_pair[0]].mark = None
                        self.state.cells[uo_pair[1]].mark = None
                    else:
                        target_cell.mark = None
                self.state.cells.append(Cell(base=ch.lower(), upper=is_upper, locked=True))
                self.state.raw.append(ch)
                self.state.raw_mode = True
                self._last_key = None
                return self._sync(ch)

            cand = self.state.clone()
            if op in TONE_OPS:
                cand.tone = op
            elif op == "TONE_CLEAR":
                if cand.tone is None:
                    continue
                cand.tone = None
            elif op == "MARK_HORN":
                uo_pair = self._find_uo_indices(cand)
                if uo_pair and idx in uo_pair:
                    cand.cells[uo_pair[0]].mark = "MARK_HORN"
                    cand.cells[uo_pair[1]].mark = "MARK_HORN"
                else:
                    cand.cells[idx].mark = "MARK_HORN"
            else:
                cand.cells[idx].mark = op

            if not is_valid_in_progress_state(cand, self.validate_mode):
                continue

            self.state = cand
            self.state.raw.append(ch)
            self.state.has_applied_op = True
            self._last_key = ch.lower()
            return self._sync(ch)

        return None

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        raw_lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        if ch in WORD_BOUNDARY_CHARS and raw_lower not in self.key_to_op:
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

        if raw_lower in self.key_to_op and self.state.cells:
            act = self._apply_vni_key(ch, is_upper)
            if act is not None:
                return act

        self._last_key = None
        if ch.isalpha():
            self.state.cells.append(Cell(base=raw_lower, upper=is_upper))
            self.state.raw.append(ch)
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
        return {"type": "vi_vni", "options": ["tone_style", "validate", "restore_invalid"]}

    def validate_pack(self, pack: Any) -> list[ValidationIssue]:
        return []


register_composer("vi_vni", ViVniComposer)