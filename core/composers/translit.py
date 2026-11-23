# core/composers/translit.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import unicodedata
from core.composers.base import Action, KeyEvent, Passthrough, Replace
from core.registry import register_composer

DEFAULT_BOUNDARIES = {
    " ", "\t", "\n", "\r", ".", ",", ";", ":", "!", "?",
    "(", ")", "[", "]", "{", "}", "\"", "'",
}


@dataclass
class _Segment:
    """Một đơn vị chuyển tự trong cụm đang gõ."""
    source: str          # Chuỗi phím gốc (chữ thường)
    output: str          # Chuỗi ký tự đích đang hiển thị
    first_upper: bool = False
    all_upper: bool = False
    finalized: bool = False
    combining_applied: Optional[str] = None  # Lưu phím dấu kết hợp vừa gắn để hoàn tác


class TranslitComposer:
    """
    Composer lõi cho Giai đoạn 3 (Cơ chế A mở rộng: Longest-Match + Prefix Buffer).
    Dùng trực tiếp cho Tiếng Nga, Hy Lạp, Ukraine... và làm lớp nền cho Tiếng Nhật (ja_kana).
    """

    requires_preedit: bool = False

    def __init__(self, pack: Any) -> None:
        self.pack = pack
        if isinstance(pack, dict):
            self.options: Dict[str, Any] = dict(pack.get("options", {}))
            self.trigger_map: Dict[str, str] = {}
            for out_ch, trigs in (pack.get("rules") or {}).items():
                trig_list = [trigs] if isinstance(trigs, str) else list(trigs)
                for t in trig_list:
                    self.trigger_map[str(t).lower()] = out_ch
            self.upper_map: Dict[str, str] = dict(pack.get("upper", {}) or {})
        else:
            self.options = dict(getattr(pack, "options", {}) or {})
            self.trigger_map = dict(getattr(pack, "trigger_map", {}) or {})
            self.upper_map = dict(getattr(pack, "upper_map", {}) or {})

        self.case_sensitive_output: bool = bool(
            self.options.get("case_sensitive_output", True)
        )
        # Hỗ trợ dấu kết hợp gắn sau nguyên âm (ví dụ dấu trọng âm tiếng Nga)
        # Format trong options: "combining_marks": {"'": {"combining": "\u0301", "bases": "аеиоуыэюя"}}
        self.combining_marks: Dict[str, Dict[str, str]] = dict(
            self.options.get("combining_marks", {}) or {}
        )

        self.max_trigger_len: int = max((len(k) for k in self.trigger_map), default=1)
        self.valid_prefixes: Set[str] = self._build_prefixes(self.trigger_map)
        self.trigger_chars: Set[str] = set()
        for k in self.trigger_map:
            self.trigger_chars.update(k)
        self.trigger_chars.update(self.combining_marks.keys())

        self.segments: List[_Segment] = []
        self.shown: str = ""

    @staticmethod
    def _build_prefixes(trigger_map: Dict[str, str]) -> Set[str]:
        prefixes: Set[str] = set()
        for key in trigger_map:
            for i in range(1, len(key)):
                prefixes.add(key[:i])
        return prefixes

    def reset(self) -> None:
        self.segments.clear()
        self.shown = ""

    def render(self) -> str:
        return "".join(seg.output for seg in self.segments)

    def _diff_action(self, old_shown: str, new_shown: str, typed_char: str) -> Action:
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

    def _apply_case(self, text: str, first_upper: bool, all_upper: bool) -> str:
        if not self.case_sensitive_output or not first_upper:
            return text
        if text in self.upper_map:
            return self.upper_map[text]
        if all_upper and len(text) > 1:
            return text.upper()
        return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    def _try_combining_mark(self, ch: str) -> Optional[Action]:
        """Gắn dấu kết hợp NFC (như trọng âm tiếng Nga \u0301) hoặc hoàn tác nếu gõ lặp."""
        spec = self.combining_marks.get(ch)
        if not spec or not self.segments:
            return None

        last = self.segments[-1]
        combining = spec.get("combining", "")
        bases = spec.get("bases", "")
        if not combining or not last.output:
            return None

        # Hoàn tác nếu vừa gắn đúng dấu này ngay trước đó
        if last.combining_applied == ch:
            nfd = unicodedata.normalize("NFD", last.output)
            if nfd.endswith(combining):
                last.output = unicodedata.normalize("NFC", nfd[: -len(combining)])
            last.combining_applied = None
            last.finalized = True
            self.segments.append(_Segment(source=ch, output=ch, finalized=True))
            return self._sync(ch)

        # Kiểm tra ký tự cuối có thuộc danh sách nguyên âm hợp lệ không
        last_char = last.output[-1]
        if last_char.lower() in bases.lower():
            marked = unicodedata.normalize("NFC", last_char + combining)
            last.output = last.output[:-1] + marked
            last.combining_applied = ch
            last.finalized = True
            return self._sync(ch)

        return None

    def _before_feed_char(self, ch: str, lower: str, is_upper: bool) -> Optional[Action]:
        """Hook cho lớp con (ví dụ JaKanaComposer xử lý sokuon & hatsuon)."""
        return None

    def feed(self, ev: KeyEvent) -> Action:
        if not ev.is_printable or not ev.char or len(ev.char) != 1:
            self.reset()
            return Passthrough()

        ch = ev.char
        lower = ch.lower()
        is_upper = ev.is_upper or (ch.isalpha() and ch.isupper())

        # 1. Xử lý dấu kết hợp (nếu có cấu hình trong pack)
        if ch in self.combining_marks:
            mark_act = self._try_combining_mark(ch)
            if mark_act is not None:
                return mark_act

        # 2. Ranh giới từ (chỉ reset nếu ký tự không nằm trong bất kỳ trigger nào)
        if ch in DEFAULT_BOUNDARIES and lower not in self.trigger_chars:
            self.reset()
            return Passthrough()

        # 3. Hook cho lớp con
        hook_act = self._before_feed_char(ch, lower, is_upper)
        if hook_act is not None:
            return hook_act

        # 4. Thử mở rộng đoạn cuối chưa chốt (Longest-Match tăng dần)
        if self.segments and not self.segments[-1].finalized:
            last = self.segments[-1]
            candidate = last.source + lower
            if len(candidate) <= self.max_trigger_len:
                if candidate in self.trigger_map:
                    last.source = candidate
                    last.all_upper = last.all_upper and (is_upper if ch.isalpha() else True)
                    last.output = self._apply_case(
                        self.trigger_map[candidate], last.first_upper, last.all_upper
                    )
                    last.finalized = candidate not in self.valid_prefixes
                    return self._sync(ch)
                if candidate in self.valid_prefixes:
                    last.source = candidate
                    last.all_upper = last.all_upper and (is_upper if ch.isalpha() else True)
                    last.output += ch
                    return self._sync(ch)
            # Không thể mở rộng thêm -> chốt đoạn trước
            last.finalized = True

        # 5. Bắt đầu đoạn mới với ký tự vừa gõ
        if lower in self.trigger_map:
            out_text = self._apply_case(self.trigger_map[lower], is_upper, is_upper)
            finalized = lower not in self.valid_prefixes
            self.segments.append(
                _Segment(
                    source=lower,
                    output=out_text,
                    first_upper=is_upper,
                    all_upper=is_upper,
                    finalized=finalized,
                )
            )
            return self._sync(ch)

        if lower in self.valid_prefixes:
            self.segments.append(
                _Segment(
                    source=lower,
                    output=ch,
                    first_upper=is_upper,
                    all_upper=is_upper,
                    finalized=False,
                )
            )
            return self._sync(ch)

        # Ký tự không nằm trong bảng chuyển tự -> giữ nguyên
        self.segments.append(_Segment(source=lower, output=ch, finalized=True))
        return self._sync(ch)

    def backspace(self) -> Action:
        if not self.segments:
            self.reset()
            return Passthrough()

        old_shown = self.shown
        last = self.segments[-1]

        if len(last.source) > 1 and not last.finalized:
            # Lùi 1 ký tự trong chuỗi đang ghép dở (ví dụ 'sh' -> 's')
            trimmed = last.source[:-1]
            last.source = trimmed
            if trimmed in self.trigger_map:
                last.output = self._apply_case(
                    self.trigger_map[trimmed], last.first_upper, last.all_upper
                )
            else:
                last.output = trimmed.upper() if last.first_upper else trimmed
        elif len(last.output) > 1:
            # Đoạn đã chốt có nhiều ký tự (như 'しゃ', 'ый') -> xóa từng ký tự cuối
            last.output = last.output[:-1]
            last.finalized = True
        else:
            self.segments.pop()

        if not self.segments:
            self.reset()
            return Passthrough()

        new_shown = self.render()
        self.shown = new_shown
        if old_shown[:-1] == new_shown:
            return Passthrough()

        common = 0
        limit = min(len(old_shown), len(new_shown))
        while common < limit and old_shown[common] == new_shown[common]:
            common += 1
        return Replace(delete_n=len(old_shown) - common, text=new_shown[common:])

    def settings_schema(self) -> dict:
        return {
            "type": "translit",
            "options": ["case_sensitive_output", "combining_marks"],
        }

    def validate_pack(self, pack: Any) -> list:
        return []


register_composer("translit", TranslitComposer)