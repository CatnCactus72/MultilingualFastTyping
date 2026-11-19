# core/pack_manager.py
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from core.conflicts.framework import ValidationIssue
from core.loader import LanguagePack, load_pack_files

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANGUAGES_DIR = PROJECT_ROOT / "languages"
DEFAULT_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DEFAULT_PACKS_DIR = DEFAULT_LANGUAGES_DIR  # Alias giữ tương thích ngược với test_m1_packs.py
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "multilingual-fasttype"

DEFAULT_BADGE_COLOR = "#1565c0"

DEFAULT_BADGE_COLOR = "#1565c0"

PACK_COLORS = {
    "ENG": DEFAULT_BADGE_COLOR,
    "PAUSED": DEFAULT_BADGE_COLOR,
    "fr": DEFAULT_BADGE_COLOR,
    "de": DEFAULT_BADGE_COLOR,
    "es": DEFAULT_BADGE_COLOR,
    "it": DEFAULT_BADGE_COLOR,
    "vi_vni": DEFAULT_BADGE_COLOR,
    "vi_telex": DEFAULT_BADGE_COLOR,
}

DEFAULT_SETTINGS = {
    "enabled_packs": ["fr", "de", "es", "it", "vi_vni", "vi_telex"],
    "hotkeys": {
        "Ctrl+Shift+F1": "fr",
        "Ctrl+Shift+F2": "de",
        "Ctrl+Shift+F3": "es",
        "Ctrl+Shift+F4": "it",
        "Ctrl+Shift+F5": "vi_vni",
        "Ctrl+Shift+F6": "vi_telex",
    },
    "notifications": True,
}


class PackManager:
    def __init__(
        self,
        packs_dir: Path = DEFAULT_LANGUAGES_DIR,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        scripts_dir: Path = DEFAULT_SCRIPTS_DIR,
    ) -> None:
        self.packs_dir = Path(packs_dir)
        self.scripts_dir = Path(scripts_dir)
        self.config_dir = Path(config_dir)
        self.overrides_dir = self.config_dir / "overrides"
        self.legacy_user_dir = self.config_dir / "user"
        self.settings_path = self.config_dir / "settings.json"
        self.packs: Dict[str, LanguagePack] = {}
        self.issues: Dict[str, List[ValidationIssue]] = {}
        self.settings: Dict[str, Any] = {}

    def ensure_config_dirs(self) -> None:
        self.overrides_dir.mkdir(parents=True, exist_ok=True)
        if not self.settings_path.exists():
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)

    def load_settings(self) -> Dict[str, Any]:
        self.ensure_config_dirs()
        with open(self.settings_path, "r", encoding="utf-8") as f:
            self.settings = json.load(f)
        return self.settings

    def save_settings(self, settings_data: Dict[str, Any]) -> None:
        self.ensure_config_dirs()
        self.settings = settings_data
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    def _resolve_pack_paths(
        self, pack_id: str
    ) -> Tuple[Path, Optional[Path], Optional[Path], Optional[Path]]:
        lang_dir = self.packs_dir / pack_id
        if not lang_dir.is_dir() and pack_id.startswith("vi_"):
            lang_dir = self.packs_dir / "vi" / pack_id

        if lang_dir.is_dir():
            manifest_path = lang_dir / "manifest.json"
            pack_name = "pack.json"
            script_id = "latn"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                pack_name = m_data.get("pack", "pack.json")
                script_id = m_data.get("script", "latn")
            base_path = lang_dir / pack_name
            script_path = self.scripts_dir / f"{script_id}.json"
        else:
            base_path = self.packs_dir / f"{pack_id}.json"
            manifest_path = None
            script_path = self.scripts_dir / "latn.json"

        override_path = self.overrides_dir / f"{pack_id}.json"
        if not override_path.exists():
            legacy_path = self.legacy_user_dir / f"{pack_id}.json"
            if legacy_path.exists():
                override_path = legacy_path

        return base_path, manifest_path, script_path, override_path
    
    def load_pack(
        self, pack_id: str
    ) -> Tuple[LanguagePack, List[ValidationIssue]]:
        base_path, manifest_path, script_path, override_path = self._resolve_pack_paths(pack_id)
        pack, pack_issues = load_pack_files(
            base_path=base_path,
            override_path=override_path if override_path and override_path.exists() else None,
            manifest_path=manifest_path if manifest_path and manifest_path.exists() else None,
            script_path=script_path if script_path and script_path.exists() else None,
        )
        self.packs[pack_id] = pack
        self.issues[pack_id] = pack_issues
        return pack, pack_issues

    def load_enabled_packs(self) -> Dict[str, LanguagePack]:
        if not self.settings:
            self.load_settings()
        self.packs.clear()
        self.issues.clear()
        for pack_id in self.settings.get("enabled_packs", []):
            self.load_pack(pack_id)
        return self.packs

    def save_user_override(
        self,
        pack_id: str,
        rules: Optional[Dict[str, List[str]]] = None,
        disable: Optional[List[str]] = None,
        upper: Optional[Dict[str, str]] = None,
        diacritics: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        bindings: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[LanguagePack, List[ValidationIssue]]:
        self.ensure_config_dirs()
        override_data: Dict[str, Any] = {
            "rules": rules or {},
            "disable": disable or [],
            "upper": upper or {},
        }
        if diacritics is not None:
            override_data["diacritics"] = diacritics
        if options is not None:
            override_data["options"] = options
        if bindings is not None:
            override_data["bindings"] = bindings

        override_path = self.overrides_dir / f"{pack_id}.json"
        with open(override_path, "w", encoding="utf-8") as f:
            json.dump(override_data, f, indent=2, ensure_ascii=False)
        return self.load_pack(pack_id)

    def get_merged_pack_dict(self, pack_id: str) -> Dict[str, Any]:
        base_path, manifest_path, _, override_path = self._resolve_pack_paths(pack_id)
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if manifest_path and manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                m_data = json.load(f)
            data.setdefault("meta", {})
            data["meta"]["id"] = m_data.get("id", pack_id)
            data["meta"]["name"] = m_data.get("name", pack_id)
            data["meta"]["symbol"] = m_data.get("badge", {}).get("label", pack_id.upper())
            data["badge"] = m_data.get("badge", {})
            data["composer"] = m_data.get("composer", "mapping")

        if override_path and override_path.exists():
            with open(override_path, "r", encoding="utf-8") as f:
                ov = json.load(f)
            if "diacritics" in ov:
                data["diacritics"] = ov["diacritics"]
            for dis in ov.get("disable", []):
                data.get("rules", {}).pop(dis, None)
            for k, v in ov.get("rules", {}).items():
                data.setdefault("rules", {})[k] = v
            for k, v in ov.get("upper", {}).items():
                data.setdefault("upper", {})[k] = v
            if "options" in ov:
                data.setdefault("options", {}).update(ov["options"])
            if "bindings" in ov:
                data["bindings"] = ov["bindings"]
        return data

    def reset_user_override(
        self, pack_id: str
    ) -> Tuple[LanguagePack, List[ValidationIssue]]:
        for directory in (self.overrides_dir, self.legacy_user_dir):
            ov_path = directory / f"{pack_id}.json"
            if ov_path.exists():
                ov_path.unlink()
        return self.load_pack(pack_id)

    @property
    def state_path(self) -> Path:
        return self.config_dir / "state.json"

    @property
    def autostart_path(self) -> Path:
        return Path.home() / ".config" / "autostart" / "multilingual-fasttype.desktop"

    def load_state(self) -> dict:
        """Đọc trạng thái hiện tại: active_pack (None hoặc mã gói) và paused (bool)."""
        self.ensure_config_dirs()
        if not self.state_path.exists():
            default_state = {"active_pack": None, "paused": False}
            self.save_state(default_state)
            return default_state
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"active_pack": None, "paused": False}

    def save_state(self, state_data: dict) -> None:
        """Lưu trạng thái để đồng bộ tức thời giữa IBus Engine và System Tray[cite: 1]."""
        self.ensure_config_dirs()
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False)

    def is_autostart_enabled(self) -> bool:
        return self.autostart_path.exists()

    def set_autostart(self, enabled: bool, _tray_script_path: Optional[Path] = None) -> None:
        """Bật/tắt tự khởi động cùng hệ thống qua chuẩn XDG Autostart (FR-14)[cite: 1, 4]."""
        self.autostart_path.parent.mkdir(parents=True, exist_ok=True)
        if enabled:
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Multilingual FastType\n"
                "Comment=Chỉ báo và điều khiển bộ gõ Multilingual FastType\n"
                "Exec=/usr/local/bin/multilingual-fasttype --silent\n"
                "Icon=/usr/share/pixmaps/multilingual-fasttype.svg\n"
                "Terminal=false\n"
                "Categories=Utility;\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            with open(self.autostart_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            if self.autostart_path.exists():
                self.autostart_path.unlink()