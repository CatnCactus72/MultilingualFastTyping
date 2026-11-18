# core/loader.py
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import unicodedata

PUNCTUATION_WARN_CHARS = set(":;,.!?'")


@dataclass
class ValidationIssue:
  level: str  # "ERROR" hoặc "WARNING"
  kind: str
  message: str


@dataclass
class LanguagePack:
  pack_id: str
  name: str
  version: int
  symbol: str
  trigger_map: Dict[str, str] = field(default_factory=dict)
  upper_map: Dict[str, str] = field(default_factory=dict)
  max_trigger_len: int = 0


class PackValidationError(Exception):

  def __init__(self, issues: List[ValidationIssue]):
    self.issues = issues
    super().__init__(
        "Gói ngôn ngữ có lỗi xung đột: "
        + "; ".join(i.message for i in issues if i.level == "ERROR")
    )


def _is_printable_ascii_no_space(s: str) -> bool:
  return bool(s) and all(33 <= ord(ch) <= 126 for ch in s)


def _expand_diacritics(
    diacritics_list: List[dict], raw_rules: Dict[str, List[str]]
) -> None:
  """Mở rộng nhóm quy tắc dấu (combining marks) thành các cặp trigger -> ký tự NFC."""
  for item in diacritics_list:
    combining = item.get("combining", "")
    triggers = item.get("triggers", [])
    bases = item.get("bases", [])
    if isinstance(triggers, str):
      triggers = [triggers]

    for base in bases:
      composed = unicodedata.normalize("NFC", base + combining)
      # Bỏ qua nếu ký tự không kết hợp được thành ký tự đơn hoặc chuỗi hợp lệ
      if composed == base:
        continue
      generated_trigs = [f"{base}{t}" for t in triggers]
      if composed in raw_rules:
        for gt in generated_trigs:
          if gt not in raw_rules[composed]:
            raw_rules[composed].append(gt)
      else:
        raw_rules[composed] = generated_trigs


def validate_raw_rules(
    rules_dict: Dict[str, List[str]],
) -> List[ValidationIssue]:
  """Kiểm tra xung đột theo mục 4.4 (FR-16)."""
  issues: List[ValidationIssue] = []
  seen_triggers: Dict[str, str] = {}

  for raw_output, triggers in rules_dict.items():
    output = unicodedata.normalize("NFC", raw_output)
    if not output:
      issues.append(
          ValidationIssue("ERROR", "EMPTY_OUTPUT", "Đầu ra không được rỗng.")
      )
      continue

    if isinstance(triggers, str):
      triggers = [triggers]

    for trig in triggers:
      if not _is_printable_ascii_no_space(trig):
        issues.append(
            ValidationIssue(
                "ERROR",
                "INVALID_TRIGGER",
                f"Trigger '{trig}' của '{output}' rỗng, chứa khoảng trắng hoặc ký tự không phải ASCII in được.",
            )
        )
        continue

      if output == trig:
        issues.append(
            ValidationIssue(
                "ERROR",
                "IDENTICAL_OUTPUT",
                f"Đầu ra '{output}' trùng đúng với trigger '{trig}'.",
            )
        )
        continue

      trig_lower = trig.lower()

      if trig_lower in seen_triggers:
        prev_out = seen_triggers[trig_lower]
        issues.append(
            ValidationIssue(
                "ERROR",
                "DUPLICATE_TRIGGER",
                f"Trùng trigger '{trig}' giữa '{prev_out}' và '{output}'.",
            )
        )
      else:
        seen_triggers[trig_lower] = output

      if len(trig) == 1:
        issues.append(
            ValidationIssue(
                "WARNING",
                "SINGLE_CHAR_TRIGGER",
                f"Trigger '{trig}' → '{output}' chỉ dài 1 ký tự; mọi lần gõ phím đó đều bị thay.",
            )
        )

      if len(trig) >= 2 and trig[-1] in PUNCTUATION_WARN_CHARS:
        issues.append(
            ValidationIssue(
                "WARNING",
                "TRAILING_PUNCTUATION",
                f"Trigger '{trig}' → '{output}' kết thúc bằng dấu câu '{trig[-1]}' thường đứng sau chữ.",
            )
        )

  all_triggers = list(seen_triggers.keys())
  for t1 in all_triggers:
    for t2 in all_triggers:
      if t1 != t2 and t2.startswith(t1):
        issues.append(
            ValidationIssue(
                "WARNING",
                "DEAD_RULE_PREFIX",
                f"Trigger '{t1}' ('{seen_triggers[t1]}') là tiền tố của '{t2}' ('{seen_triggers[t2]}'); quy tắc '{t2}' sẽ không bao giờ chạy.",
            )
        )

  return issues


def build_pack_from_dict(
    base_data: dict, override_data: Optional[dict] = None
) -> Tuple[LanguagePack, List[ValidationIssue]]:
  """Gộp gói gốc (diacritics + rules) và file ghi đè (FR-18), kiểm tra xung đột."""
  meta = base_data.get("meta", {})
  raw_rules: Dict[str, List[str]] = {}

  # 1. Mở rộng nhóm dấu (diacritics) trước
  if "diacritics" in base_data:
    _expand_diacritics(base_data["diacritics"], raw_rules)

  # 2. Nạp các quy tắc rời (rules)
  for out, trigs in base_data.get("rules", {}).items():
    norm_out = unicodedata.normalize("NFC", out)
    trig_list = [trigs] if isinstance(trigs, str) else list(trigs)
    if norm_out in raw_rules:
      for t in trig_list:
        if t not in raw_rules[norm_out]:
          raw_rules[norm_out].append(t)
    else:
      raw_rules[norm_out] = trig_list

  upper_map: Dict[str, str] = {
      unicodedata.normalize("NFC", k): unicodedata.normalize("NFC", v)
      for k, v in base_data.get("upper", {}).items()
  }

  # 3. Áp dụng file ghi đè của người dùng (FR-18)
  if override_data:
    for disabled_out in override_data.get("disable", []):
      norm_dis = unicodedata.normalize("NFC", disabled_out)
      raw_rules.pop(norm_dis, None)

    if "diacritics" in override_data:
      _expand_diacritics(override_data["diacritics"], raw_rules)

    for out, trigs in override_data.get("rules", {}).items():
      norm_out = unicodedata.normalize("NFC", out)
      raw_rules[norm_out] = [trigs] if isinstance(trigs, str) else list(trigs)

    for k, v in override_data.get("upper", {}).items():
      upper_map[unicodedata.normalize("NFC", k)] = unicodedata.normalize(
          "NFC", v
      )

  issues = validate_raw_rules(raw_rules)
  errors = [i for i in issues if i.level == "ERROR"]
  if errors:
    raise PackValidationError(issues)

  trigger_map: Dict[str, str] = {}
  max_len = 0
  for out, trigs in raw_rules.items():
    for t in trigs:
      t_low = t.lower()
      trigger_map[t_low] = out
      if len(t_low) > max_len:
        max_len = len(t_low)

  pack = LanguagePack(
      pack_id=meta.get("id", "unknown"),
      name=meta.get("name", "Unknown"),
      version=meta.get("version", 1),
      symbol=meta.get("symbol", "??"),
      trigger_map=trigger_map,
      upper_map=upper_map,
      max_trigger_len=max_len,
  )
  return pack, issues


def load_pack_files(
    base_path: Path, override_path: Optional[Path] = None
) -> Tuple[LanguagePack, List[ValidationIssue]]:
  with open(base_path, "r", encoding="utf-8") as f:
    base_data = json.load(f)
  override_data = None
  if override_path and override_path.exists():
    with open(override_path, "r", encoding="utf-8") as f:
      override_data = json.load(f)
  return build_pack_from_dict(base_data, override_data)