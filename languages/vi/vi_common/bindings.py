# languages/vi/bindings.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from core.conflicts.framework import ValidationIssue
from languages.vi.vi_common.state import ALL_VI_OPS, OP_TARGETS
from languages.vi.vi_common.syllables import POST_VOWEL_LETTERS

RESERVED_CONTROL_CHARS = {" ", "\t", "\n", "\r", "\x1b", "\x08", "\x7f"}
SENTENCE_PUNCTUATION = {".", ",", ";", ":", "!", "?", "\"", "(", ")"}

PRESET_TELEX: List[Dict[str, Any]] = [
    {"op": "TONE_SAC",   "triggers": [{"key": "s"}]},
    {"op": "TONE_HUYEN", "triggers": [{"key": "f"}]},
    {"op": "TONE_HOI",   "triggers": [{"key": "r"}]},
    {"op": "TONE_NGA",   "triggers": [{"key": "x"}]},
    {"op": "TONE_NANG",  "triggers": [{"key": "j"}]},
    {"op": "TONE_CLEAR", "triggers": [{"key": "z"}]},
    {"op": "MARK_CIRC",  "triggers": [{"repeat": "a"}, {"repeat": "e"}, {"repeat": "o"}]},
    {"op": "MARK_HORN",  "triggers": [{"key": "w"}]},
    {"op": "MARK_BREVE", "triggers": [{"key": "w"}]},
    {"op": "STROKE_D",   "triggers": [{"repeat": "d"}]},
]

PRESET_VNI: List[Dict[str, Any]] = [
    {"op": "TONE_SAC",   "triggers": [{"key": "1"}]},
    {"op": "TONE_HUYEN", "triggers": [{"key": "2"}]},
    {"op": "TONE_HOI",   "triggers": [{"key": "3"}]},
    {"op": "TONE_NGA",   "triggers": [{"key": "4"}]},
    {"op": "TONE_NANG",  "triggers": [{"key": "5"}]},
    {"op": "TONE_CLEAR", "triggers": [{"key": "0"}]},
    {"op": "MARK_CIRC",  "triggers": [{"key": "6"}]},
    {"op": "MARK_HORN",  "triggers": [{"key": "7"}]},
    {"op": "MARK_BREVE", "triggers": [{"key": "8"}]},
    {"op": "STROKE_D",   "triggers": [{"key": "9"}]},
]


@dataclass(frozen=True)
class ViTriggerSpec:
    op: str
    kind: str  # "key" | "repeat"
    char: str  # Chữ thường dài 1 ký tự


def parse_bindings(raw_bindings: List[Dict[str, Any]]) -> List[ViTriggerSpec]:
    specs: List[ViTriggerSpec] = []
    for item in raw_bindings:
        op = item.get("op", "")
        for trig in item.get("triggers", []):
            if "key" in trig:
                specs.append(ViTriggerSpec(op=op, kind="key", char=str(trig["key"]).lower()))
            elif "repeat" in trig:
                specs.append(ViTriggerSpec(op=op, kind="repeat", char=str(trig["repeat"]).lower()))
    return specs


def validate_vi_bindings_static(
    raw_bindings: List[Dict[str, Any]],
    advanced_punctuation: bool = False,
) -> List[ValidationIssue]:
    """Kiểm tra tĩnh C-VI-01 đến C-VI-06 (Phụ lục A.5)."""
    issues: List[ValidationIssue] = []
    key_to_ops: Dict[str, List[str]] = {}
    op_covered_targets: Dict[str, Set[str]] = {op: set() for op in ALL_VI_OPS}

    for item in raw_bindings:
        op = item.get("op", "")
        if op not in ALL_VI_OPS:
            continue
        triggers = item.get("triggers", [])
        for trig in triggers:
            kind = "repeat" if "repeat" in trig else "key"
            raw_val = str(trig.get(kind, ""))
            ch = raw_val.lower()

            # C-VI-04: Trigger phải là 1 ký tự duy nhất, không phải phím điều khiển
            if len(ch) != 1 or ch in RESERVED_CONTROL_CHARS or not ch.isprintable():
                issues.append(ValidationIssue(
                    code="C-VI-04",
                    level="ERROR",
                    message=f"Trigger '{raw_val}' của {op} phải là 1 ký tự in được duy nhất (không phải phím điều khiển).",
                    context=raw_val,
                ))
                continue

            # C-VI-05: Dấu câu kết thúc câu không được dùng làm phím dấu (trừ chế độ nâng cao)
            if not advanced_punctuation and ch in SENTENCE_PUNCTUATION:
                issues.append(ValidationIssue(
                    code="C-VI-05",
                    level="ERROR",
                    message=f"Ký tự dấu câu '{ch}' không được dùng làm phím dấu cho {op}.",
                    context=ch,
                ))

            # C-VI-06: Ký hiệu và chữ số làm phím dấu -> Cảnh báo
            if not ch.isalpha() and ch not in SENTENCE_PUNCTUATION:
                issues.append(ValidationIssue(
                    code="C-VI-06",
                    level="WARNING",
                    message=f"Phím '{ch}' ({op}) là chữ số/ký hiệu: cần gõ hai lần để xuất ký tự gốc ngay sau nguyên âm.",
                    context=ch,
                ))

            # C-VI-02: Phím chữ cái loại 'key' không được thuộc tập chữ đứng sau nguyên âm
            if kind == "key" and ch.isalpha() and ch in POST_VOWEL_LETTERS:
                issues.append(ValidationIssue(
                    code="C-VI-02",
                    level="ERROR",
                    message=f"Phím chữ cái '{ch}' ({op}) thuộc tập chữ cái đứng sau nguyên âm trong tiếng Việt.",
                    context=ch,
                ))

            # Ghi nhận độ phủ đích cho C-VI-03
            if kind == "key":
                op_covered_targets[op].update(OP_TARGETS[op])
                key_to_ops.setdefault(f"key:{ch}", []).append(op)
            else:
                if ch in OP_TARGETS[op]:
                    op_covered_targets[op].add(ch)
                key_to_ops.setdefault(f"repeat:{ch}:{op}", []).append(op)
                # Kiểm tra nếu 1 repeat gán cho 2 op khác nhau trên cùng chữ cái
                key_to_ops.setdefault(f"repeat_char:{ch}", []).append(op)

    # C-VI-01: Một phím gán cho nhiều phép toán thì tập đích phải rời nhau
    for key_tag, ops in key_to_ops.items():
        if key_tag.startswith("repeat:"):
            continue
        unique_ops = list(dict.fromkeys(ops))
        if len(unique_ops) > 1:
            for i in range(len(unique_ops)):
                for j in range(i + 1, len(unique_ops)):
                    op1, op2 = unique_ops[i], unique_ops[j]
                    overlap = OP_TARGETS[op1] & OP_TARGETS[op2]
                    if overlap:
                        ch_disp = key_tag.split(":")[-1]
                        issues.append(ValidationIssue(
                            code="C-VI-01",
                            level="ERROR",
                            message=f"Phím '{ch_disp}' gán cho cả {op1} và {op2} có chung chữ đích: {', '.join(sorted(overlap))}.",
                            context=ch_disp,
                        ))

    # C-VI-03: Thiếu phủ (mỗi phép toán phải gõ được toàn bộ đích của nó)
    for op in ALL_VI_OPS:
        missing = OP_TARGETS[op] - op_covered_targets.get(op, set())
        if missing:
            issues.append(ValidationIssue(
                code="C-VI-03",
                level="ERROR",
                message=f"Phép toán {op} chưa phủ hết các chữ đích: thiếu {', '.join(sorted(missing))}.",
                context=op,
            ))

    return issues