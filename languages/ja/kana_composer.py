# languages/ja/kana_composer.py
from typing import Any, Optional
from core.composers.base import Action
from core.composers.translit import TranslitComposer
from core.registry import register_composer

SOKUON_CONSONANTS = {
    "b", "c", "d", "f", "g", "h", "j", "k", "m", "p", "q", "r", "s", "t", "v", "w", "z",
}
VOWELS_AND_Y = {"a", "i", "u", "e", "o", "y"}


class JaKanaComposer(TranslitComposer):
    """Composer dùng chung cho Hiragana và Katakana (kế thừa TranslitComposer)."""

    def __init__(self, pack: Any) -> None:
        super().__init__(pack)
        self.case_sensitive_output = False
        self.sokuon_enabled: bool = bool(self.options.get("double_consonant_sokuon", True))
        self.sokuon_char: str = str(self.options.get("sokuon_char", "っ"))
        self.hatsuon_char: str = str(self.options.get("hatsuon_char", "ん"))

    def _before_feed_char(self, ch: str, lower: str, is_upper: bool) -> Optional[Action]:
        if not self.segments:
            return None

        last = self.segments[-1]
        if last.finalized:
            return None

        # 1. Âm mũi 'n' đứng trước phụ âm không tạo thành hàng N (ví dụ senpai -> せんぱい)
        if (
            last.source == "n"
            and lower not in VOWELS_AND_Y
            and lower not in ("n", "'")
            and lower.isalpha()
        ):
            last.output = self.hatsuon_char
            last.finalized = True
            return None

        # 2. Gấp đôi phụ âm thành sokuon (っ / ッ), ví dụ kka -> っか, tta -> った
        if (
            self.sokuon_enabled
            and len(last.source) == 1
            and last.source in SOKUON_CONSONANTS
            and lower == last.source
        ):
            last.output = self.sokuon_char
            last.finalized = True
            return None

        return None

    def settings_schema(self) -> dict:
        return {
            "type": "ja_kana",
            "options": ["double_consonant_sokuon", "sokuon_char", "hatsuon_char"],
        }


register_composer("ja_kana", JaKanaComposer)