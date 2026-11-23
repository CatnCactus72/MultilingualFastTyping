# languages/ja/romaji_table.py
from typing import Dict

# Bảng ánh xạ Romaji chuẩn -> Hiragana (ưu tiên khớp chuỗi dài nhất ở composer.py)
HIRAGANA_ROMAJI_MAP: Dict[str, str] = {
    # Nguyên âm đơn
    "a": "あ",
    "i": "い",
    "u": "う",
    "e": "え",
    "o": "お",

    # Hàng K & G (đục)
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",

    # Hàng S & Z/J (đục)
    "sa": "さ", "shi": "し", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ",
    "za": "ざ", "ji": "じ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",

    # Hàng T & D/C (đục)
    "ta": "た", "chi": "ち", "ti": "ち", "tsu": "つ", "tu": "つ", "te": "て", "to": "と",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "dya": "ぢゃ", "dyu": "ぢゅ", "dyo": "ぢょ",

    # Hàng N
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",

    # Hàng H, B (đục) & P (bán đục)
    "ha": "は", "hi": "ひ", "fu": "ふ", "hu": "ふ", "he": "へ", "ho": "ほ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",

    # Hàng M
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",

    # Hàng Y
    "ya": "や", "yu": "ゆ", "yo": "よ",

    # Hàng R
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",

    # Hàng W & Âm mũi N
    "wa": "わ", "wo": "を",
    "n'": "ん", "nn": "ん",
}

MAX_ROMAJI_LEN: int = max((len(k) for k in HIRAGANA_ROMAJI_MAP), default=3)

# Phụ âm có thể gấp đôi thành っ (sokuon) khi đứng trước chính nó (trừ 'n')
SOKUON_CONSONANTS = {
    "b", "c", "d", "f", "g", "h", "j", "k", "m", "p", "q", "r", "s", "t", "v", "w", "z"
}

# Các phụ âm không phải nguyên âm hay 'y' (khi theo sau 'n' đơn lẻ mà không tạo thành âm hàng N)
VOWELS_AND_Y = {"a", "i", "u", "e", "o", "y"}