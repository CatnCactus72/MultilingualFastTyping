# languages/ja/kanji/converter.py
from typing import List


class KanjiCandidateConverter:
    """Khung mở rộng chuyển đổi Kana/Romaji -> ứng viên Kanji ở giai đoạn sau."""

    def get_candidates(self, kana_reading: str, limit: int = 9) -> List[str]:
        return []