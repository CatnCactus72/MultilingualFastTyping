# core/composers/mapping.py
from typing import Any, Dict, List, Optional, Set, Tuple
from core.composers.base import Action, Composer, KeyEvent, Passthrough, Replace
from core.conflicts.framework import ValidationIssue
from core.conflicts.generic_rules import validate_generic_rules
from core.registry import register_composer

DEFAULT_WORD_BOUNDARIES = {
    " ", "\t", "\n", "\r", ".", ",", ";", ":", "!", "?",
    "(", ")", "[", "]", "{", "}", "\"", "'"
}


class MappingComposer:
    """Composer Cơ chế A: Ánh xạ chuỗi phím sang ký tự (Pháp, Đức, Tây Ban Nha, Ý...)."""

    requires_preedit: bool = False

    def __init__(self, pack: Any) -> None:
        self.pack = pack
        self.buffer: List[Tuple[str, bool]] = []  # [(raw_char_lower, is_upper), ...]
        self.last_match: Optional[Dict[str, Any]] = None
        self.locked_triggers: Set[str] = set()

    def reset(self) -> None:
        self.buffer.clear()
        self.last_match = None
        self.locked_triggers.clear()

    def render(self) -> str:
        return "".join(ch.upper() if up else ch for ch, up in self.buffer)

    def backspace(self) -> Action:
        # Theo Mục 4.2 bản gốc: Backspace ở Cơ chế A xóa bộ đệm an toàn
        self.reset()
        return Passthrough()

    def _apply_case(self, base_output: str, is_upper: bool) -> str:
        if not is_upper:
            return base_output
        custom_upper = getattr(self.pack, "upper_map", {}) or {}
        if base_output in custom_upper:
            return custom_upper[base_output]
        return base_output.upper()

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        raw_lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        trigger_map: Dict[str, str] = getattr(self.pack, "trigger_map", {})
        max_len: int = getattr(self.pack, "max_trigger_len", 20)

        # 1. Kiểm tra Hoàn tác (FR-15): gõ lặp phím cuối của trigger vừa kích hoạt
        if self.last_match is not None:
            last_trig: str = self.last_match["trigger"]
            if raw_lower == last_trig[-1]:
                out_str: str = self.last_match["output"]
                raw_typed: str = self.last_match["raw_typed"]
                self.locked_triggers.add(last_trig)
                self.last_match = None
                # Khôi phục buffer về chuỗi phím thô
                self.buffer = [(c.lower(), c.isupper()) for c in raw_typed]
                return Replace(delete_n=len(out_str), text=raw_typed)

        # Nếu là ký tự ranh giới từ và không nằm trong bất kỳ trigger nào -> xóa bộ đệm
        trigger_chars = getattr(self.pack, "trigger_chars", set())
        if ch in DEFAULT_WORD_BOUNDARIES and raw_lower not in trigger_chars:
            self.reset()
            return Passthrough()

        # 2. Thêm phím mới vào bộ đệm
        self.buffer.append((raw_lower, is_upper))
        if len(self.buffer) > max(max_len * 2, 20):
            self.buffer = self.buffer[-max(max_len * 2, 20):]

        buf_lower = "".join(c for c, _ in self.buffer)

        # 3. Tìm quy tắc khớp ở hậu tố của buffer
        # Ưu tiên khớp ngắn nhất / khớp ngay khi gõ đủ trigger
        for length in range(1, min(len(self.buffer), max_len) + 1):
            suffix = buf_lower[-length:]
            if suffix in trigger_map and suffix not in self.locked_triggers:
                base_out = trigger_map[suffix]
                matched_slice = self.buffer[-length:]

                # Xác định hoa/thường dựa trên phím chữ cái đầu tiên trong trigger (FR-08)
                first_alpha_upper = False
                for raw_c, up_flag in matched_slice:
                    if raw_c.isalpha():
                        first_alpha_upper = up_flag
                        break

                final_out = self._apply_case(base_out, first_alpha_upper)
                raw_typed_str = "".join(
                    c.upper() if u else c for c, u in matched_slice
                )

                # Thay các ký tự của trigger trong buffer bằng ký tự kết quả
                del self.buffer[-length:]
                for out_ch in final_out:
                    self.buffer.append((out_ch.lower(), out_ch.isupper()))

                self.last_match = {
                    "trigger": suffix,
                    "output": final_out,
                    "raw_typed": raw_typed_str,
                }
                # delete_n = số ký tự của trigger đã hiển thị trước phím hiện tại
                return Replace(delete_n=length - 1, text=final_out)

        self.last_match = None
        return Passthrough()

    def settings_schema(self) -> dict:
        return {
            "type": "mapping",
            "supports_diacritics": True,
            "supports_rules": True,
        }

    def validate_pack(self, pack: Any) -> List[ValidationIssue]:
        raw_rules = getattr(pack, "raw_rules", {}) if not isinstance(pack, dict) else pack.get("rules", {})
        return validate_generic_rules(raw_rules)


# Đăng ký vào Registry (Mục 3.4)
register_composer("mapping", MappingComposer)
register_composer("rules", MappingComposer)