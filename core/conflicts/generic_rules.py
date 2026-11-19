# core/conflicts/generic_rules.py
from typing import Dict, List, Optional, Set
from core.conflicts.framework import ValidationIssue

RESERVED_TRIGGERS = {
    " ", "\t", "\n", "\r", "\x1b", "\x08", "\x7f"
}
BOUNDARY_CHARS = {".", ",", ";", ":", "!", "?", "(", ")", "[", "]", "{", "}"}


def validate_generic_rules(
    rules: Dict[str, List[str]],
    required_chars: Optional[Set[str]] = None,
    allow_boundary_triggers: bool = False,
    longest_prefix_mode: bool = False,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    trigger_to_outputs: Dict[str, List[str]] = {}

    # G-01, G-03, G-04, G-07
    for output, triggers in rules.items():
        for trig in triggers:
            if not trig or any(ch in RESERVED_TRIGGERS for ch in trig):
                issues.append(ValidationIssue(
                    code="G-03",
                    level="ERROR",
                    message=f"Trigger '{trig}' cho '{output}' rỗng hoặc chứa phím điều khiển/khoảng trắng.",
                    context=trig,
                ))
                continue

            if not allow_boundary_triggers and any(ch in BOUNDARY_CHARS for ch in trig):
                # Cho phép ký tự lặp dấu câu như '??', '!!' nếu không kết thúc từ thông thường
                if len(set(trig)) > 1 or len(trig) == 1:
                    issues.append(ValidationIssue(
                        code="G-04",
                        level="ERROR",
                        message=f"Trigger '{trig}' chứa ký tự ranh giới từ (chỉ cho phép ở chế độ nâng cao).",
                        context=trig,
                    ))

            if any(ch.isdigit() or (not ch.isalnum() and ch not in BOUNDARY_CHARS) for ch in trig):
                issues.append(ValidationIssue(
                    code="G-07",
                    level="WARNING",
                    message=f"Trigger '{trig}' chứa chữ số/ký hiệu (cần gõ lặp để ra ký tự gốc).",
                    context=trig,
                ))

            trigger_to_outputs.setdefault(trig, []).append(output)

    # G-01: Trùng trigger khác đầu ra
    for trig, outs in trigger_to_outputs.items():
        unique_outs = list(dict.fromkeys(outs))
        if len(unique_outs) > 1:
            issues.append(ValidationIssue(
                code="G-01",
                level="ERROR",
                message=f"Trùng trigger '{trig}' cho các đầu ra khác nhau: {', '.join(unique_outs)}.",
                context=trig,
            ))

    # G-02: Quy tắc bị che khuất (tiền tố)
    all_triggers = sorted(trigger_to_outputs.keys(), key=len)
    for i, short_t in enumerate(all_triggers):
        for long_t in all_triggers[i + 1:]:
            if long_t.startswith(short_t) and long_t != short_t:
                issues.append(ValidationIssue(
                    code="G-02" if longest_prefix_mode else "G-02",
                    level="WARNING" if longest_prefix_mode else "ERROR",
                    message=f"Trigger '{long_t}' bị che khuất bởi trigger ngắn hơn '{short_t}'.",
                    context=long_t,
                ))

    # G-05: Chuỗi thay thế vòng (A -> B -> A)
    single_char_map: Dict[str, str] = {}
    for output, triggers in rules.items():
        for trig in triggers:
            if len(trig) == 1 and len(output) == 1 and trig != output:
                single_char_map[trig] = output

    for start_ch in single_char_map:
        visited = set()
        curr = start_ch
        while curr in single_char_map:
            if curr in visited:
                issues.append(ValidationIssue(
                    code="G-05",
                    level="ERROR",
                    message=f"Phát hiện chuỗi thay thế vòng bắt đầu từ '{start_ch}'.",
                    context=start_ch,
                ))
                break
            visited.add(curr)
            curr = single_char_map[curr]

    # G-06: Kiểm tra phủ ký tự bắt buộc
    if required_chars:
        covered = set(rules.keys())
        missing = sorted(required_chars - covered)
        if missing:
            issues.append(ValidationIssue(
                code="G-06",
                level="ERROR",
                message=f"Thiếu quy tắc cho các ký tự bắt buộc: {', '.join(missing)}.",
            ))

    return issues