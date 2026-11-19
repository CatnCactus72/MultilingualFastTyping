# languages/vi/vi_common/roundtrip.py
from typing import Any, Callable, Dict, List, Optional
from core.composers.base import Composer
from core.conflicts.framework import ValidationIssue
from core.registry import get_composer_class
from core.testing.roundtrip import run_roundtrip_harness
from languages.vi.vi_common.bindings import PRESET_VNI, ViTriggerSpec, parse_bindings
from languages.vi.vi_common.phonotactics import render_word_state
from languages.vi.vi_common.state import (
    TONE_OPS,
    Cell,
    ViWordState,
    decompose_vietnamese_char,
)
from languages.vi.vi_common.syllables import ONSET_RIME_MAP, STOP_CODAS


def _string_to_cells(text: str) -> List[Cell]:
    cells: List[Cell] = []
    for ch in text:
        base, is_up, mark, _ = decompose_vietnamese_char(ch)
        cells.append(Cell(base=base, upper=is_up, mark=mark))
    return cells


def enumerate_valid_syllables(
    tone_style: str = "modern",
    include_tones: bool = True,
) -> List[str]:
    """Liệt kê toàn bộ âm tiết tiếng Việt hợp lệ (kể cả biến thể thanh điệu) chuẩn NFC."""
    results: List[str] = []
    tones: List[Optional[str]] = [None] + list(TONE_OPS) if include_tones else [None]

    for onset, rimes in sorted(ONSET_RIME_MAP.items()):
        for rime in sorted(rimes):
            if onset == "gi" and rime.startswith("i"):
                full_base = "g" + rime
            else:
                full_base = onset + rime

            base_cells = _string_to_cells(full_base)
            is_stop = rime.endswith(STOP_CODAS)

            for tone in tones:
                if is_stop and tone not in ("TONE_SAC", "TONE_NANG"):
                    continue
                state = ViWordState(cells=[c.clone() for c in base_cells], tone=tone)
                rendered = render_word_state(state, tone_style=tone_style)
                results.append(rendered)
    return results


def _build_op_trigger_lookup(specs: List[ViTriggerSpec]) -> Dict[str, List[ViTriggerSpec]]:
    by_op: Dict[str, List[ViTriggerSpec]] = {}
    for s in specs:
        by_op.setdefault(s.op, []).append(s)
    return by_op


def _pick_trigger_for_op(
    by_op: Dict[str, List[ViTriggerSpec]],
    op: str,
    base_char: str,
) -> ViTriggerSpec:
    candidates = by_op.get(op, [])
    for c in candidates:
        if c.kind == "repeat" and c.char == base_char:
            return c
    for c in candidates:
        if c.kind == "key":
            return c
    return candidates[0]


def encode_syllable(
    syllable: str,
    raw_bindings: List[Dict[str, Any]],
    style: str = "tone_end",
) -> str:
    """Sinh chuỗi phím gõ cho một âm tiết theo bảng gán phím hiện tại."""
    specs = parse_bindings(raw_bindings)
    by_op = _build_op_trigger_lookup(specs)
    repeat_chars_for_circ = {
        s.char for s in by_op.get("MARK_CIRC", []) if s.kind == "repeat"
    }

    decomp = [decompose_vietnamese_char(ch) for ch in syllable]
    found_tone: Optional[str] = None
    for _, _, _, t in decomp:
        if t is not None:
            found_tone = t
            break

    last_vowel_idx = -1
    for i, (b, _, m, _) in enumerate(decomp):
        if b in ("a", "e", "i", "o", "u", "y") and m != "STROKE_D":
            last_vowel_idx = i

    keystrokes: List[str] = []

    for i, (base, is_up, mark, _) in enumerate(decomp):
        typed_base = base.upper() if is_up else base
        keystrokes.append(typed_base)

        if (
            i > 0
            and mark is None
            and decomp[i - 1][0] == base
            and decomp[i - 1][2] is None
            and base in repeat_chars_for_circ
        ):
            keystrokes.append(base)

        if mark is not None:
            if not (
                mark == "MARK_HORN"
                and base == "u"
                and i + 1 < len(decomp)
                and decomp[i + 1][0] == "o"
                and decomp[i + 1][2] == "MARK_HORN"
            ):
                trig = _pick_trigger_for_op(by_op, mark, base)
                keystrokes.append(trig.char)

        if found_tone is not None and i == last_vowel_idx:
            if style in ("immediate", "tone_before_coda"):
                tone_trig = _pick_trigger_for_op(by_op, found_tone, base).char
                keystrokes.append(tone_trig)

    if found_tone is not None and style == "tone_end":
        tone_trig = _pick_trigger_for_op(by_op, found_tone, "a").char
        keystrokes.append(tone_trig)

    return "".join(keystrokes)


def validate_vi_roundtrip_c07(
    pack: Any,
    composer_factory: Optional[Callable[[], Composer]] = None,
    sample_only: bool = False,
) -> List[ValidationIssue]:
    """Kiểm tra C-VI-07 dùng chung cho cả vi_vni và vi_telex."""
    if isinstance(pack, dict):
        options = pack.get("options", {})
        raw_bindings = pack.get("bindings") or PRESET_VNI
        composer_name = pack.get("composer", "vi_vni")
    else:
        options = getattr(pack, "options", {}) or {}
        raw_bindings = getattr(pack, "bindings", None) or PRESET_VNI
        composer_name = getattr(pack, "composer", "vi_vni")

    if composer_factory is None:
        comp_cls = get_composer_class(composer_name)
        composer_factory = lambda: comp_cls(pack)

    tone_style = options.get("tone_style", "modern")
    syllables = enumerate_valid_syllables(tone_style=tone_style, include_tones=True)
    if sample_only:
        syllables = syllables[::10]

    failures = run_roundtrip_harness(
        composer_factory=composer_factory,
        valid_items=syllables,
        encoder=lambda item, st: encode_syllable(item, raw_bindings, style=st),
        styles=("tone_end", "immediate", "tone_before_coda"),
        max_failures=5,
    )

    issues: List[ValidationIssue] = []
    for fail in failures:
        issues.append(
            ValidationIssue(
                code="C-VI-07",
                level="ERROR",
                message=(
                    f"Test vòng thất bại ở '{fail.expected}' "
                    f"(kiểu {fail.style}, gõ '{fail.keystrokes}' -> ra '{fail.actual}')."
                ),
                context=fail.expected,
            )
        )
    return issues