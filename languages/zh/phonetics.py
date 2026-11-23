from typing import List, Optional, Set
from core.composers.marks import MarkCell, SyllableBuffer

PINYIN_INITIALS: Set[str] = {
    "b", "p", "m", "f",
    "d", "t", "n", "l",
    "g", "k", "h",
    "j", "q", "x",
    "zh", "ch", "sh", "r",
    "z", "c", "s",
    "y", "w",
}

PINYIN_VOWELS: Set[str] = {"a", "e", "i", "o", "u", "ü"}

# Tập âm tiết Pinyin chuẩn phổ biến (dạng chữ cơ sở không thanh điệu, dùng 'ü' cho âm /y/)
PINYIN_SYLLABLES: Set[str] = {
    # Zero initial (a, o, e, er)
    "a", "ai", "an", "ang", "ao",
    "o", "ou",
    "e", "ei", "en", "eng", "er",
    # b, p, m, f
    "ba", "bai", "ban", "bang", "bao", "bei", "ben", "beng", "bi", "bian", "biao", "bie", "bin", "bing", "bo", "bu",
    "pa", "pai", "pan", "pang", "pao", "pei", "pen", "peng", "pi", "pian", "piao", "pie", "pin", "ping", "po", "pu",
    "ma", "mai", "man", "mang", "mao", "me", "mei", "men", "meng", "mi", "mian", "miao", "mie", "min", "ming", "miu", "mo", "mou", "mu",
    "fa", "fan", "fang", "fei", "fen", "feng", "fo", "fou", "fu",
    # d, t, n, l
    "da", "dai", "dan", "dang", "dao", "de", "dei", "den", "deng", "di", "dia", "dian", "diao", "die", "ding", "diu", "dong", "dou", "du", "duan", "dui", "dun", "duo",
    "ta", "tai", "tan", "tang", "tao", "te", "teng", "ti", "tian", "tiao", "tie", "ting", "tong", "tou", "tu", "tuan", "tui", "tun", "tuo",
    "na", "nai", "nan", "nang", "nao", "ne", "nei", "nen", "neng", "ni", "nian", "niang", "niao", "nie", "nin", "ning", "niu", "nong", "nou", "nu", "nü", "nuan", "nüe", "nuo",
    "la", "lai", "lan", "lang", "lao", "le", "lei", "leng", "li", "lia", "lian", "liang", "liao", "lie", "lin", "ling", "liu", "long", "lou", "lu", "lü", "luan", "lüe", "lun", "luo",
    # g, k, h
    "ga", "gai", "gan", "gang", "gao", "ge", "gei", "gen", "geng", "gong", "gou", "gu", "gua", "guai", "guan", "guang", "gui", "gun", "guo",
    "ka", "kai", "kan", "kang", "kao", "ke", "ken", "keng", "kong", "kou", "ku", "kua", "kuai", "kuan", "kuang", "kui", "kun", "kuo",
    "ha", "hai", "han", "hang", "hao", "he", "hei", "hen", "heng", "hong", "hou", "hu", "hua", "huai", "huan", "huang", "hui", "hun", "huo",
    # j, q, x
    "ji", "jia", "jian", "jiang", "jiao", "jie", "jin", "jing", "jiong", "jiu", "ju", "juan", "jue", "jun",
    "qi", "qia", "qian", "qiang", "qiao", "qie", "qin", "qing", "qiong", "qiu", "qu", "quan", "que", "qun",
    "xi", "xia", "xian", "xiang", "xiao", "xie", "xin", "xing", "xiong", "xiu", "xu", "xuan", "xue", "xun",
    # zh, ch, sh, r
    "zha", "zhai", "zhan", "zhang", "zhao", "zhe", "zhei", "zhen", "zheng", "zhi", "zhong", "zhou", "zhu", "zhua", "zhuai", "zhuan", "zhuang", "zhui", "zhun", "zhuo",
    "cha", "chai", "chan", "chang", "chao", "che", "chen", "cheng", "chi", "chong", "chou", "chu", "chua", "chuai", "chuan", "chuang", "chui", "chun", "chuo",
    "sha", "shai", "shan", "shang", "shao", "she", "shei", "shen", "sheng", "shi", "shou", "shu", "shua", "shuai", "shuan", "shuang", "shui", "shun", "shuo",
    "ran", "rang", "rao", "re", "ren", "reng", "ri", "rong", "rou", "ru", "rua", "ruan", "rui", "run", "ruo",
    # z, c, s
    "za", "zai", "zan", "zang", "zao", "ze", "zei", "zen", "zeng", "zi", "zong", "zou", "zu", "zuan", "zui", "zun", "zuo",
    "ca", "cai", "can", "cang", "cao", "ce", "cen", "ceng", "ci", "cong", "cou", "cu", "cuan", "cui", "cun", "cuo",
    "sa", "sai", "san", "sang", "sao", "se", "sen", "seng", "si", "song", "sou", "su", "suan", "sui", "sun", "suo",
    # y, w
    "ya", "yan", "yang", "yao", "ye", "yi", "yin", "ying", "yong", "you", "yu", "yuan", "yue", "yun",
    "wa", "wai", "wan", "wang", "wei", "wen", "weng", "wo", "wu",
}

# Tiền tố hợp lệ của các âm tiết Pinyin chuẩn
PINYIN_PREFIXES: Set[str] = {
    syl[:i]
    for syl in PINYIN_SYLLABLES
    for i in range(1, len(syl) + 1)
}


def cells_to_pinyin_key(cells: List[MarkCell]) -> str:
    """Chuyển danh sách MarkCell của 1 âm tiết sang dạng khóa tra bảng âm tiết Pinyin."""
    chars: List[str] = []
    for c in cells:
        b = c.base.lower()
        if c.mark == "MARK_DIAERESIS" and b == "u":
            chars.append("ü")
        else:
            chars.append(b)
    return "".join(chars)


def select_pinyin_tone_index(syllable: SyllableBuffer) -> Optional[int]:
    """
    Quy tắc đặt dấu thanh chuẩn Pinyin:
    1. Có 'a', 'o', 'e' -> ưu tiên theo thứ tự a > o > e.
    2. Có 'iu' -> đặt ở 'u'; có 'ui' -> đặt ở 'i'.
    3. Còn lại -> đặt ở nguyên âm cuối cùng trong âm tiết.
    """
    vowel_indices = [
        i for i, c in enumerate(syllable.cells) if c.base in PINYIN_VOWELS
    ]
    if not vowel_indices:
        return None

    for priority_vowel in ("a", "o", "e"):
        for idx in vowel_indices:
            if syllable.cells[idx].base == priority_vowel:
                return idx

    seq = "".join(syllable.cells[i].base for i in vowel_indices)
    if "iu" in seq:
        pos = seq.index("iu") + 1
        return vowel_indices[pos]
    if "ui" in seq:
        pos = seq.index("ui") + 1
        return vowel_indices[pos]

    return vowel_indices[-1]


def is_valid_pinyin_syllable(
    syllable: SyllableBuffer,
    strict: bool = True,
    require_complete: bool = False,
) -> bool:
    if not syllable.cells:
        return False
    has_vowel = any(c.base in PINYIN_VOWELS for c in syllable.cells)
    if syllable.tone and not has_vowel:
        return False
    if not strict:
        return has_vowel or len(syllable.cells) <= 2

    key = cells_to_pinyin_key(syllable.cells)
    if require_complete or syllable.locked_final:
        return key in PINYIN_SYLLABLES
    return key in PINYIN_PREFIXES


def can_append_to_pinyin_syllable(
    current: SyllableBuffer, next_lower: str
) -> bool:
    """Kiểm tra `next_lower` có thể nối tiếp vào âm tiết hiện tại hay cần tách sang âm tiết mới."""
    if not current.cells:
        return True
    if current.locked_final:
        return False
    if not any(c.base in PINYIN_VOWELS for c in current.cells):
        # Chưa có nguyên âm (vd: đang gõ phụ âm đầu 'zh', 'c', 'm'...)
        cand_key = cells_to_pinyin_key(current.cells) + next_lower
        return cand_key in PINYIN_PREFIXES

    # Đã có nguyên âm: nếu âm tiết hiện tại đã là một âm tiết hoàn chỉnh
    # và ký tự tiếp theo KHÔNG thể nối tiếp thành tiền tố âm tiết hợp lệ (vd: 'cong' + 'm')
    # -> tách sang âm tiết mới.
    cur_key = cells_to_pinyin_key(current.cells)
    cand_key = cur_key + next_lower
    if cur_key in PINYIN_SYLLABLES and cand_key not in PINYIN_PREFIXES:
        return False
    return cand_key in PINYIN_PREFIXES