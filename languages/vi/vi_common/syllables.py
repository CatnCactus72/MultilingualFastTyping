# languages/vi/syllables.py
from typing import Dict, Set, Tuple
import unicodedata

# Phụ âm đầu sắp xếp từ dài đến ngắn để phân tích tham lam (Mục 4.8c)
INITIALS: Tuple[str, ...] = (
    "ngh",
    "ng", "nh", "ph", "th", "tr", "ch", "kh", "gh", "gi", "qu",
    "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x",
)

# Phụ âm cuối hợp lệ
CODAS: Tuple[str, ...] = ("ch", "ng", "nh", "c", "m", "n", "p", "t")

# Phụ âm cuối thanh nhập: chỉ nhận thanh Sắc hoặc Nặng (Quy tắc cứng H3)
STOP_CODAS: Tuple[str, ...] = ("c", "ch", "p", "t")

FRONT_VOWELS: Set[str] = {"i", "y", "e", "ê"}
BACK_CENTRAL_VOWELS: Set[str] = {"a", "ă", "â", "o", "ô", "ơ", "u", "ư"}
NO_LABIALIZED_INITIALS: Set[str] = {"b", "m", "ph", "v", "r", "gi", "qu"}

# Tập chữ cái có thể đứng sau nguyên âm trong âm tiết hợp lệ (dùng cho C-VI-02)
POST_VOWEL_LETTERS: Set[str] = {
    "a", "e", "i", "o", "u", "y",
    "c", "g", "h", "m", "n", "p", "t",
}

STANDARD_RIMES: Tuple[str, ...] = tuple(
    unicodedata.normalize("NFC", r)
    for r in (
        # Nhóm a
        "a", "ac", "ach", "ai", "am", "an", "ang", "anh", "ao", "ap", "at", "au", "ay",
        # Nhóm ă (luôn có âm cuối)
        "ăc", "ăm", "ăn", "ăng", "ăp", "ăt",
        # Nhóm â (luôn có âm cuối)
        "âc", "âm", "ân", "âng", "âp", "ât", "âu", "ây",
        # Nhóm e
        "e", "ec", "em", "en", "eng", "eo", "ep", "et",
        # Nhóm ê
        "ê", "êch", "êm", "ên", "ênh", "êp", "êt", "êu",
        # Nhóm i / iê
        "i", "ia", "ich", "iêc", "iêm", "iên", "iêng", "iêp", "iêt", "iêu",
        "im", "in", "inh", "ip", "it", "iu",
        # Nhóm o / oa / oă / oe
        "o", "oa", "oac", "oach", "oai", "oam", "oan", "oang", "oanh", "oao", "oap", "oat", "oay",
        "oăc", "oăm", "oăn", "oăng", "oăp", "oăt",
        "oc", "oe", "oen", "oeo", "oet", "oi", "om", "on", "ong", "ooc", "oong", "op", "ot",
        # Nhóm ô
        "ô", "ôc", "ôi", "ôm", "ôn", "ông", "ôp", "ôt",
        # Nhóm ơ
        "ơ", "ơi", "ơm", "ơn", "ơp", "ơt",
        # Nhóm u / ua / uâ / uê / uô / uơ / uy
        "u", "ua", "uâc", "uân", "uâng", "uât", "uây",
        "uc", "uê", "uêch", "uên", "uênh", "uêt", "uêu",
        "ui", "um", "un", "ung", "uôc", "uôi", "uôm", "uôn", "uông", "uôt",
        "uơ",
        "up", "ut", "uy", "uya", "uych", "uyên", "uyêt", "uyn", "uynh", "uyp", "uyt", "uyu",
        # Nhóm ư / ưa / ươ
        "ư", "ưa", "ưc", "ưi", "ưm", "ưn", "ưng",
        "ươc", "ươi", "ươm", "ươn", "ương", "ươp", "ươt", "ươu", "ưt", "ưu",
        # Nhóm y / yê
        "y", "yêm", "yên", "yêng", "yêt", "yêu",
    )
)

RIME_SET: Set[str] = set(STANDARD_RIMES)


def _is_labialized_rime(rime: str) -> bool:
    return rime.startswith(("oa", "oă", "oe", "uâ", "uê", "uy", "uơ"))


def is_valid_onset_rime(initial: str, rime: str) -> bool:
    if not rime or rime not in RIME_SET:
        return False

    first_vowel = rime[0]

    # 1. k, gh, ngh chỉ đứng trước i, y, e, ê (gh, ngh không đi với y)
    if initial in ("k", "gh", "ngh"):
        if first_vowel not in FRONT_VOWELS:
            return False
        if initial in ("gh", "ngh") and first_vowel == "y":
            return False

    # 2. c, g, ng đứng trước a, ă, â, o, ô, ơ, u, ư
    if initial in ("c", "g", "ng"):
        if first_vowel not in BACK_CENTRAL_VOWELS:
            return False

    # 3. Sau 'qu' không đi với vần bắt đầu bằng o, ô, ơ, u, ư
    if initial == "qu" and first_vowel in ("o", "u", "ô", "ơ", "ư"):
        return False

    # 4. Phụ âm môi và r, gi, qu không đi với âm đệm tròn môi
    if initial in NO_LABIALIZED_INITIALS and _is_labialized_rime(rime):
        return False

    # 5. Ngoại lệ vần mở 'uơ' chỉ đi với h, th, kh, qu (qu đã lọc ở trên)
    if rime == "uơ" and initial not in ("h", "th", "kh"):
        return False

    # 6. Âm đầu rỗng với y: chỉ dùng cho y, yêm, yên, yêng, yêt, yêu
    if initial == "" and first_vowel == "y" and rime not in ("y", "yêm", "yên", "yêng", "yêt", "yêu"):
        return False

    # 7. Sau phụ âm đầu (khác rỗng và khác qu), vần bắt đầu bằng y chỉ có 'y'
    if initial not in ("", "qu") and first_vowel == "y" and rime != "y":
        return False

    return True


def build_onset_rime_map() -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for onset in ("",) + INITIALS:
        mapping[onset] = {r for r in STANDARD_RIMES if is_valid_onset_rime(onset, r)}
    return mapping


ONSET_RIME_MAP: Dict[str, Set[str]] = build_onset_rime_map()