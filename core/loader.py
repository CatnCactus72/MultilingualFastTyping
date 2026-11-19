# core/loader.py
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from core.conflicts.framework import ValidationIssue
from core.conflicts.generic_rules import validate_generic_rules
from core.layers.unicode_utils import normalize_text
from core.registry import get_composer_class


@dataclass
class LanguagePack:
    id: str
    name: str
    version: int = 1
    symbol: str = ""
    badge: Dict[str, str] = field(default_factory=dict)
    script: str = "latn"
    composer: str = "mapping"
    direction: str = "ltr"
    stage: int = 1
    schema: int = 1
    normalization: str = "NFC"
    word_boundaries: List[str] = field(default_factory=list)
    raw_rules: Dict[str, List[str]] = field(default_factory=dict)
    diacritics: List[Dict[str, Any]] = field(default_factory=list)
    trigger_map: Dict[str, str] = field(default_factory=dict)
    upper_map: Dict[str, str] = field(default_factory=dict)
    max_trigger_len: int = 1
    trigger_chars: Set[str] = field(default_factory=set)
    # Dành cho cơ chế B (Tiếng Việt) và các giai đoạn sau
    options: Dict[str, Any] = field(default_factory=dict)
    bindings: List[Dict[str, Any]] = field(default_factory=list)


def _normalize_triggers_list(val: Union[str, List[str]]) -> List[str]:
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


def expand_diacritics_to_rules(
    diacritics: List[Dict[str, Any]],
    normalization: str = "NFC",
) -> Dict[str, List[str]]:
    """Mở rộng nhóm dấu kết hợp (base + combining) thành quy tắc chuẩn hóa NFC (Mục 4.2)."""
    expanded: Dict[str, List[str]] = {}
    for group in diacritics:
        combining = group.get("combining", "")
        triggers = _normalize_triggers_list(group.get("triggers", []))
        bases = group.get("bases") or group.get("vowels") or []
        if not combining or not triggers or not bases:
            continue
        for base in bases:
            composed = normalize_text(f"{base}{combining}", normalization)
            out_trigs = expanded.setdefault(composed, [])
            for t in triggers:
                trig_str = f"{base}{t}".lower()
                if trig_str not in out_trigs:
                    out_trigs.append(trig_str)
    return expanded


def merge_pack_layers(
    script_data: Optional[Dict[str, Any]],
    manifest_data: Optional[Dict[str, Any]],
    pack_data: Dict[str, Any],
    override_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Hợp nhất 3 tầng dữ liệu: Hồ sơ hệ chữ (scripts/) -> Gói ngôn ngữ (languages/) -> Ghi đè (overrides/)."""
    script_data = script_data or {}
    manifest_data = manifest_data or {}
    override_data = override_data or {}

    meta = pack_data.get("meta", {})
    pack_id = manifest_data.get("id") or pack_data.get("id") or meta.get("id", "unknown")
    name = manifest_data.get("name") or pack_data.get("name") or meta.get("name", pack_id)
    # symbol = (
    #     manifest_data.get("badge", {}).get("label")
    #     or meta.get("symbol")
    #     or pack_id.upper()[:2]
    # )
    # badge = manifest_data.get("badge") or {
    #     "label": symbol,
    #     "color": "#1565c0",
    # }
    raw_badge = manifest_data.get("badge")
    if isinstance(raw_badge, str):
        symbol = raw_badge
        badge = {"label": symbol}
    elif isinstance(raw_badge, dict):
        symbol = raw_badge.get("label") or meta.get("symbol") or pack_id.upper()[:3]
        badge = {"label": symbol}
    else:
        symbol = meta.get("symbol") or pack_id.upper()[:3]
        badge = {"label": symbol}
        
    # Hợp nhất diacritics
    diacritics = list(script_data.get("diacritics", []))
    if "diacritics" in pack_data:
        diacritics = list(pack_data["diacritics"])
    if "diacritics" in override_data:
        diacritics = list(override_data["diacritics"])

    # Hợp nhất rules
    rules: Dict[str, Union[str, List[str]]] = {}
    for src in (script_data.get("rules", {}), pack_data.get("rules", {})):
        for k, v in src.items():
            rules[k] = _normalize_triggers_list(v)

    # Áp dụng disable từ override
    disabled = set(override_data.get("disable", []))
    for dis_key in disabled:
        rules.pop(dis_key, None)

    # Áp dụng rules ghi đè
    for k, v in override_data.get("rules", {}).items():
        rules[k] = _normalize_triggers_list(v)

    # Hợp nhất upper
    upper: Dict[str, str] = {}
    for src in (
        script_data.get("upper", {}),
        pack_data.get("upper", {}),
        override_data.get("upper", {}),
    ):
        upper.update(src)

    # Hợp nhất options & bindings (cho composer kiểu vietnamese)
    options = dict(pack_data.get("options", {}))
    options.update(override_data.get("options", {}))

    bindings = override_data.get("bindings", pack_data.get("bindings", []))

    return {
        "id": pack_id,
        "name": name,
        "version": meta.get("version", 1),
        "symbol": symbol,
        "badge": badge,
        "script": manifest_data.get("script", script_data.get("script", "latn")),
        "composer": manifest_data.get("composer", pack_data.get("composer", "mapping")),
        "direction": manifest_data.get("direction", "ltr"),
        "stage": manifest_data.get("stage", 1),
        "schema": manifest_data.get("schema", pack_data.get("schema", 1)),
        "normalization": script_data.get("normalization", "NFC"),
        "word_boundaries": script_data.get("word_boundaries", []),
        "diacritics": diacritics,
        "rules": rules,
        "disable": list(disabled),
        "upper": upper,
        "options": options,
        "bindings": bindings,
    }


def build_pack_from_dict(
    data: Dict[str, Any],
    override_data: Optional[Dict[str, Any]] = None,
    script_data: Optional[Dict[str, Any]] = None,
    manifest_data: Optional[Dict[str, Any]] = None,
) -> Tuple[LanguagePack, List[ValidationIssue]]:
    merged = merge_pack_layers(script_data, manifest_data, data, override_data)
    norm_form = merged.get("normalization", "NFC")
    disabled_set = set(merged.get("disable", []))

    # 1. Mở rộng diacritics
    combined_rules: Dict[str, List[str]] = expand_diacritics_to_rules(
        merged.get("diacritics", []), norm_form
    )
    for dis in disabled_set:
        combined_rules.pop(normalize_text(dis, norm_form), None)

    # 2. Gộp với rules trực tiếp (nếu override định nghĩa lại ký tự trong diacritics thì thay thế)
    raw_rules_input = merged.get("rules", {})
    override_rules_keys = set((override_data or {}).get("rules", {}).keys())

    for out_char, trigs in raw_rules_input.items():
        norm_out = normalize_text(out_char, norm_form)
        norm_trigs = [normalize_text(t, norm_form).lower() for t in _normalize_triggers_list(trigs)]
        if norm_out in override_rules_keys or norm_out not in combined_rules:
            combined_rules[norm_out] = norm_trigs
        else:
            existing = combined_rules[norm_out]
            for t in norm_trigs:
                if t not in existing:
                    existing.append(t)

    upper_map = {
        normalize_text(k, norm_form): normalize_text(v, norm_form)
        for k, v in merged.get("upper", {}).items()
    }

    # 3. Kiểm tra xung đột
    composer_name = merged.get("composer", "mapping")
    issues: List[ValidationIssue] = []

    if composer_name in ("mapping", "rules"):
        issues.extend(validate_generic_rules(combined_rules))
    else:
        try:
            comp_cls = get_composer_class(composer_name)
            comp_instance = comp_cls(merged)
            issues.extend(comp_instance.validate_pack(merged))
        except KeyError:
            pass

    # 4. Xây dựng trigger_map (chỉ nạp các quy tắc hợp lệ không bị lỗi G-01/G-03)
    error_triggers = {
        iss.context for iss in issues if iss.level == "ERROR" and iss.context
    }
    trigger_map: Dict[str, str] = {}
    max_len = 1
    trigger_chars: Set[str] = set()

    for out_char, trigs in combined_rules.items():
        for trig in trigs:
            if not trig or trig in error_triggers:
                continue
            if trig not in trigger_map:
                trigger_map[trig] = out_char
                max_len = max(max_len, len(trig))
                trigger_chars.update(trig)

    pack = LanguagePack(
        id=merged["id"],
        name=merged["name"],
        version=merged["version"],
        symbol=merged["symbol"],
        badge=merged["badge"],
        script=merged["script"],
        composer=composer_name,
        direction=merged["direction"],
        stage=merged["stage"],
        schema=merged["schema"],
        normalization=norm_form,
        word_boundaries=merged["word_boundaries"],
        raw_rules=combined_rules,
        diacritics=merged.get("diacritics", []),
        trigger_map=trigger_map,
        upper_map=upper_map,
        max_trigger_len=max_len,
        trigger_chars=trigger_chars,
        options=merged.get("options", {}),
        bindings=merged.get("bindings", []),
    )
    return pack, issues


def load_pack_files(
    base_path: Path,
    override_path: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    script_path: Optional[Path] = None,
) -> Tuple[LanguagePack, List[ValidationIssue]]:
    with open(base_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    override_data = None
    if override_path and override_path.exists():
        with open(override_path, "r", encoding="utf-8") as f:
            override_data = json.load(f)

    manifest_data = None
    if manifest_path and manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

    script_data = None
    if script_path and script_path.exists():
        with open(script_path, "r", encoding="utf-8") as f:
            script_data = json.load(f)

    return build_pack_from_dict(
        base_data,
        override_data=override_data,
        script_data=script_data,
        manifest_data=manifest_data,
    )