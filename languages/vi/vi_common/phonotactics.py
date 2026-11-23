# languages/vi/phonotactics.py
from dataclasses import dataclass
from typing import List, Optional, Tuple
from languages.vi.vi_common.state import Cell, VOWEL_BASES, ViWordState, compose_cell_char, decompose_vietnamese_char
from languages.vi.vi_common.syllables import CODAS, INITIALS, ONSET_RIME_MAP, RIME_SET, STOP_CODAS
from core.composers.marks import MarkCell

@dataclass(frozen=True)
class ParsedSyllable:
    onset: str                  # Chuỗi phụ âm đầu đã có dấu ('đ', 'ngh', 'gi', 'qu'...)
    onset_indices: List[int]
    nucleus_indices: List[int]  # Chỉ số các ô nguyên âm thuộc nhân
    coda: str                   # Chuỗi phụ âm cuối ('c', 'ch', 'ng'...)
    coda_indices: List[int]
    extra_indices: List[int]    # Các ô không khớp cấu trúc chuẩn


def parse_cells(cells: List[Cell]) -> ParsedSyllable:
    """Phân tích danh sách Cell thành (onset, nucleus, coda) theo Mục 4.8c."""
    n = len(cells)
    if n == 0:
        return ParsedSyllable("", [], [], "", [], [])

    marked_str = "".join(c.marked_lower() for c in cells)

    # 1. Tách phụ âm đầu (tham lam từ dài đến ngắn)
    onset = ""
    onset_len = 0
    for ini in INITIALS:
        if marked_str.startswith(ini):
            if ini == "gi":
                # 'gi' là phụ âm đầu nếu theo sau còn nguyên âm (già, gió).
                # Nếu đứng một mình hoặc theo sau là phụ âm cuối (gì, gìn) thì 'g' là đầu, 'i' là nhân.
                rest = cells[2:]
                if rest and rest[0].base in VOWEL_BASES:
                    onset = "gi"
                    onset_len = 2
                else:
                    onset = "g"
                    onset_len = 1
            elif ini == "qu":
                onset = "qu"
                onset_len = 2
            else:
                onset = ini
                onset_len = len(ini)
            break

    onset_indices = list(range(onset_len))

    # 2. Tách chuỗi nguyên âm (nhân)
    idx = onset_len
    nucleus_indices: List[int] = []
    while idx < n and cells[idx].base in VOWEL_BASES and cells[idx].mark != "STROKE_D":
        nucleus_indices.append(idx)
        idx += 1

    # 3. Tách âm cuối
    coda_indices = list(range(idx, n))
    coda_str = "".join(cells[i].marked_lower() for i in coda_indices)
    extra_indices: List[int] = []

    if coda_str and coda_str not in CODAS:
        # Đang gõ dở hoặc âm cuối không hợp lệ
        extra_indices = coda_indices
        coda_indices = []
        coda_str = ""

    return ParsedSyllable(
        onset=onset,
        onset_indices=onset_indices,
        nucleus_indices=nucleus_indices,
        coda=coda_str,
        coda_indices=coda_indices,
        extra_indices=extra_indices,
    )


def select_tone_index(
    cells: List[Cell],
    parsed: ParsedSyllable,
    tone_style: str = "modern",
) -> Optional[int]:
    """Chọn chỉ số ô nhận dấu thanh theo đúng 6 thứ tự ưu tiên ở Mục 4.8c."""
    nuc = parsed.nucleus_indices
    if not nuc:
        return None

    # 1. Một nguyên âm: đặt vào nó
    if len(nuc) == 1:
        return nuc[0]

    has_coda = bool(parsed.coda_indices or parsed.extra_indices)

    # 2. Có nguyên âm mang dấu chữ (â ê ô ơ ư ă): đặt vào nguyên âm có dấu cuối cùng (ươ -> ơ, uyê -> ê)
    marked_vowels = [i for i in nuc if cells[i].mark is not None]
    if marked_vowels:
        return marked_vowels[-1]

    bases = "".join(cells[i].base for i in nuc)

    # 3. ia, ya, ua (không dấu, không âm cuối): nguyên âm đầu
    if not has_coda and bases in ("ia", "ya", "ua"):
        return nuc[0]

    # 4. oa, oe, uy:
    #    - Có âm cuối (toán, huỳnh): luôn vào chữ thứ hai (nuc[1])
    #    - Không âm cuối: theo spec mục 4.3 (modern: hòa, thủy -> nuc[0] | classic: hoà, thuỷ -> nuc[1])
    if bases in ("oa", "oe", "uy"):
        if has_coda:
            return nuc[1]
        return nuc[0] if tone_style == "modern" else nuc[1]

    # 5. Ba nguyên âm không dấu (oai, oay, uai, oeo, uyu, uya, oao): nguyên âm giữa
    if len(nuc) == 3:
        return nuc[1]

    # 6. Hai nguyên âm còn lại (ai, ao, au, ay, eo, iu, oi, ui, oo...): nguyên âm đầu
    return nuc[0]


def render_word_state(state: ViWordState, tone_style: str = "modern") -> str:
    """Hàm thuần (pure function) biến ViWordState thành chuỗi NFC (Mục 4.8a, 4.8c)."""
    if not state.cells:
        return ""

    parsed = parse_cells(state.cells)
    tone_idx = select_tone_index(state.cells, parsed, tone_style) if state.tone else None

    # Quy tắc 4.8c: cặp 'ươ' mở (không âm cuối) in thành 'uơ' (huơ, thuở)
    open_uo_horn = False
    nuc = parsed.nucleus_indices
    if (
        len(nuc) == 2
        and not parsed.coda_indices
        and not parsed.extra_indices
        and state.cells[nuc[0]].base == "u"
        and state.cells[nuc[0]].mark == "MARK_HORN"
        and state.cells[nuc[1]].base == "o"
        and state.cells[nuc[1]].mark == "MARK_HORN"
        and parsed.onset in ("h", "th", "kh")
    ):
        open_uo_horn = True

    out_chars: List[str] = []
    for idx, cell in enumerate(state.cells):
        effective_mark = cell.mark
        if open_uo_horn and idx == nuc[0]:
            effective_mark = None
        cell_tone = state.tone if idx == tone_idx else None
        out_chars.append(
            compose_cell_char(cell.base, cell.upper, effective_mark, cell_tone)
        )
    return "".join(out_chars)


def _strip_marks_from_rime(rime: str) -> Tuple[str, List[Optional[str]]]:
    bases = []
    marks = []
    for ch in rime:
        b, _, m, _ = decompose_vietnamese_char(ch)
        bases.append(b)
        marks.append(m)
    return "".join(bases), marks


def is_valid_complete_syllable(
    state: ViWordState,
    validate_mode: str = "strict",
) -> bool:
    """Kiểm tra âm tiết đã hoàn chỉnh có hợp lệ không (dùng cho khôi phục từ sai ở ranh giới từ)."""
    if validate_mode == "off":
        return True
    if not state.cells:
        return True

    parsed = parse_cells(state.cells)
    if not parsed.nucleus_indices or parsed.extra_indices:
        return False

    # Kiểm tra phụ âm không nằm ngoài vị trí
    if validate_mode == "relaxed":
        # Relaxed: chỉ cần có nhân nguyên âm và thỏa quy tắc cứng H3 nếu có âm cuối tắc
        if parsed.coda in STOP_CODAS and state.tone not in ("TONE_SAC", "TONE_NANG", None):
            return False
        return True

    # Strict: kiểm tra phụ âm đầu + vần trong ONSET_RIME_MAP và quy tắc cứng H3
    rendered_no_tone = render_word_state(
        ViWordState(cells=state.cells, tone=None), tone_style="modern"
    ).lower()

    onset = parsed.onset
    if onset not in ONSET_RIME_MAP:
        return False

    if onset == "g" and len(state.cells) >= 2 and state.cells[0].marked_lower() == "g" and state.cells[1].marked_lower() == "i":
        # 'gì', 'gìn': onset thực chất là 'gi' và rime bắt đầu bằng 'i'
        effective_onset = "gi"
        rime = rendered_no_tone[1:]
    else:
        effective_onset = onset
        rime = rendered_no_tone[len(onset):]

    if rime not in ONSET_RIME_MAP.get(effective_onset, set()):
        return False

    # Quy tắc cứng H3: âm tiết kết thúc c, ch, p, t chỉ được mang thanh sắc hoặc nặng
    if parsed.coda in STOP_CODAS and state.tone not in ("TONE_SAC", "TONE_NANG"):
        return False

    return True


def is_valid_in_progress_state(
    state: ViWordState,
    validate_mode: str = "strict",
) -> bool:
    """
    Kiểm tra trạng thái đang gõ V(s) theo Mục 4.8e:
    Tồn tại âm tiết hợp lệ mà phần chữ hiện tại là tiền tố,
    các dấu hiện có là tập con dấu của nó, và thanh hiện có tương thích.
    """
    if validate_mode == "off":
        return True
    if not state.cells:
        return True

    parsed = parse_cells(state.cells)

    if validate_mode == "relaxed":
        # Relaxed: chỉ cần có nguyên âm đích (hoặc 'đ') và không vi phạm H3
        if parsed.coda in STOP_CODAS and state.tone not in (None, "TONE_SAC", "TONE_NANG"):
            return False
        return True

    # Strict mode
    # Nếu chỉ mới gõ phụ âm đầu (ví dụ 'đ') mà chưa có nguyên âm
    if not parsed.nucleus_indices:
        marked_str = "".join(c.marked_lower() for c in state.cells)
        if state.tone is not None:
            return False
        return any(ini.startswith(marked_str) for ini in INITIALS)

    # Nếu có ký tự sau nhân mà không phải tiền tố của bất kỳ CODAS nào -> sai
    tail_indices = parsed.coda_indices + parsed.extra_indices
    tail_str = "".join(state.cells[i].marked_lower() for i in tail_indices)
    if tail_str and not any(coda.startswith(tail_str) for coda in CODAS):
        return False

    # Nếu âm cuối đã hoàn chỉnh là c, ch, p, t (và không phải tiền tố của ng/nh/ch mang thanh khác)
    # Lưu ý: 'c' có thể là tiền tố của 'ch' (vẫn là stop coda), 'n' có thể là tiền tố của 'ng'/'nh'
    if tail_str in STOP_CODAS and state.tone not in (None, "TONE_SAC", "TONE_NANG"):
        return False

    onset = parsed.onset
    if onset not in ONSET_RIME_MAP:
        return False

    if onset == "g" and state.cells[parsed.nucleus_indices[0]].base == "i":
        candidate_pairs = [("gi", state.cells[1:])]
    elif onset == "gi":
        candidate_pairs = [
            ("gi", state.cells[2:]),  # Cho 'gi' + 'a', 'o', 'u'... (già, gió, giường)
            ("gi", state.cells[1:]),  # Cho 'gi' + 'iê...' (giếng, giết, giếc)
        ]
    else:
        candidate_pairs = [(onset, state.cells[len(onset):])]

    for cand_onset, rime_cells in candidate_pairs:
        typed_bases = "".join(c.base for c in rime_cells)
        typed_marks = [c.mark for c in rime_cells]

        for valid_rime in ONSET_RIME_MAP.get(cand_onset, set()):
            v_bases, v_marks = _strip_marks_from_rime(valid_rime)
            if not v_bases.startswith(typed_bases):
                continue

            # Kiểm tra các dấu hiện có là tập con dấu của vần đích
            marks_compatible = True
            for idx, t_mark in enumerate(typed_marks):
                if t_mark is not None and t_mark != v_marks[idx]:
                    if valid_rime == "uơ" and idx == 0 and t_mark == "MARK_HORN":
                        continue
                    marks_compatible = False
                    break
            if not marks_compatible:
                continue

            # Kiểm tra thanh hiện có tương thích với vần đích (H3)
            if state.tone in ("TONE_HUYEN", "TONE_HOI", "TONE_NGA"):
                if valid_rime.endswith(STOP_CODAS):
                    continue

            return True

    return False

def _to_vi_cells(cells: List[MarkCell]) -> List[Cell]:
    return [Cell(base=c.base, upper=c.upper, mark=c.mark, locked=c.locked) for c in cells]


def select_vi_tone_index(
    cells: List[MarkCell], tone_style: str = "modern"
) -> Optional[int]:
    vi_cells = _to_vi_cells(cells)
    parsed = parse_cells(vi_cells)
    return select_tone_index(vi_cells, parsed, tone_style)


def is_valid_in_progress_cells(
    cells: List[MarkCell],
    tone: Optional[str],
    strict: bool = True,
    require_complete: bool = False,
) -> bool:
    mode = "strict" if strict else "relaxed"
    vi_state = ViWordState(cells=_to_vi_cells(cells), tone=tone)
    if require_complete:
        return is_valid_complete_syllable(vi_state, mode)
    return is_valid_in_progress_state(vi_state, mode)


def render_vi_cells(
    cells: List[MarkCell], tone: Optional[str], tone_style: str = "modern"
) -> str:
    vi_state = ViWordState(cells=_to_vi_cells(cells), tone=tone)
    return render_word_state(vi_state, tone_style)