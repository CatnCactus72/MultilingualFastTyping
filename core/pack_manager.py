# core/pack_manager.py
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from core.conflicts.framework import ValidationIssue
from core.loader import LanguagePack, load_language_plugin, load_pack_files

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANGUAGES_DIR = PROJECT_ROOT / "languages"
DEFAULT_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DEFAULT_PACKS_DIR = DEFAULT_LANGUAGES_DIR
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "multilingual-fasttype"
USER_LANGUAGES_DIR = Path.home() / ".local" / "share" / "multilingual-fasttype" / "languages"

DEFAULT_BADGE_COLOR = "#1565c0"

DEFAULT_SETTINGS = {
    "enabled_packs": [
        "fr", "de", "es", "it",
        "vi_vni", "vi_telex",
        "zh_pinyin", "ru", "ja_hiragana",
    ],
    "hotkeys": {
        "Ctrl+Shift+F1": "fr",
        "Ctrl+Shift+F2": "de",
        "Ctrl+Shift+F3": "es",
        "Ctrl+Shift+F4": "it",
        "Ctrl+Shift+F5": "vi_vni",
        "Ctrl+Shift+F6": "vi_telex",
        "Ctrl+Shift+F7": "zh_pinyin",
        "Ctrl+Shift+F8": "ru",
        "Ctrl+Shift+F9": "ja_hiragana",
    },
    "notifications": True,
}

class PackManager:
    def __init__(
        self,
        packs_dir: Path = DEFAULT_LANGUAGES_DIR,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        scripts_dir: Path = DEFAULT_SCRIPTS_DIR,
        user_packs_dir: Optional[Path] = USER_LANGUAGES_DIR,
    ) -> None:
        self.packs_dir = Path(packs_dir)
        self.user_packs_dir = Path(user_packs_dir) if user_packs_dir else None
        self.scripts_dir = Path(scripts_dir)
        self.config_dir = Path(config_dir)
        self.overrides_dir = self.config_dir / "overrides"
        self.legacy_user_dir = self.config_dir / "user"
        self.settings_path = self.config_dir / "settings.json"

        self.packs: Dict[str, LanguagePack] = {}
        self.issues: Dict[str, List[ValidationIssue]] = {}
        self.settings: Dict[str, Any] = {}
        # Ánh xạ mode_id -> (lang_dir, manifest_dict_cho_mode)
        self._mode_index: Dict[str, Tuple[Path, Dict[str, Any]]] = {}

    def _language_search_dirs(self) -> List[Path]:
        dirs = [self.packs_dir]
        if self.user_packs_dir and self.user_packs_dir != self.packs_dir:
            dirs.append(self.user_packs_dir)
        return dirs

    def discover_modes(self) -> Dict[str, Tuple[Path, Dict[str, Any]]]:
        """Quét tất cả thư mục ngôn ngữ cài sẵn & cài thêm, nạp plugin và lập chỉ mục các mode."""
        self._mode_index.clear()
        for base_dir in self._language_search_dirs():
            if not base_dir.is_dir():
                continue
            for lang_dir in sorted(base_dir.iterdir()):
                if not lang_dir.is_dir() or lang_dir.name.startswith((".", "_")):
                    continue
                manifest_path = lang_dir / "manifest.json"
                if not manifest_path.exists():
                    continue

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                # Nạp động plugin Python của ngôn ngữ nếu có
                entry_file = manifest.get("entry", "__init__.py")
                load_language_plugin(lang_dir, entry_file)

                if "modes" in manifest and isinstance(manifest["modes"], list):
                    for mode in manifest["modes"]:
                        mode_id = mode["id"]
                        merged_manifest = {
                            "id": mode_id,
                            "name": mode.get("name", manifest.get("name", mode_id)),
                            "script": mode.get("script", manifest.get("script", "latn")),
                            "composer": mode.get("composer", manifest.get("composer", "mapping")),
                            "direction": mode.get("direction", manifest.get("direction", "ltr")),
                            "stage": mode.get("stage", manifest.get("stage", 1)),
                            "badge": mode.get("badge", manifest.get("badge", {"label": mode_id.upper()[:3]})),
                            "pack": mode.get("pack", "pack.json"),
                            "schema": manifest.get("schema", 2),
                        }
                        self._mode_index[mode_id] = (lang_dir, merged_manifest)
                else:
                    mode_id = manifest.get("id", lang_dir.name)
                    self._mode_index[mode_id] = (lang_dir, manifest)

        return self._mode_index

    def list_available_packs(self) -> List[Tuple[str, str]]:
        """Trả về danh sách [(mode_id, 'Tên hiển thị (BADGE)')] cho GUI."""
        if not self._mode_index:
            self.discover_modes()
        result: List[Tuple[str, str]] = []
        for mode_id, (_, m) in self._mode_index.items():
            badge = m.get("badge", {})
            label = badge.get("label", mode_id.upper()[:3]) if isinstance(badge, dict) else str(badge)
            result.append((mode_id, f"{m.get('name', mode_id)} ({label})"))
        return result

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
    ) -> Tuple[Path, Optional[Dict[str, Any]], Optional[Path], Optional[Path]]:
        if not self._mode_index:
            self.discover_modes()

        if pack_id in self._mode_index:
            lang_dir, manifest_dict = self._mode_index[pack_id]
            base_path = lang_dir / manifest_dict.get("pack", "pack.json")
            script_id = manifest_dict.get("script", "latn")
            script_path = self.scripts_dir / f"{script_id}.json"
        else:
            # Fallback cho thư mục con cũ hoặc file phẳng
            lang_dir = self.packs_dir / pack_id
            if not lang_dir.is_dir() and pack_id.startswith("vi_"):
                lang_dir = self.packs_dir / "vi" / pack_id
            if lang_dir.is_dir():
                load_language_plugin(lang_dir.parent if lang_dir.parent.name == "vi" else lang_dir)
                m_file = lang_dir / "manifest.json"
                manifest_dict = json.loads(m_file.read_text(encoding="utf-8")) if m_file.exists() else None
                pack_name = (manifest_dict or {}).get("pack", "pack.json")
                script_id = (manifest_dict or {}).get("script", "latn")
                base_path = lang_dir / pack_name
                script_path = self.scripts_dir / f"{script_id}.json"
            else:
                base_path = self.packs_dir / f"{pack_id}.json"
                manifest_dict = None
                script_path = self.scripts_dir / "latn.json"

        override_path = self.overrides_dir / f"{pack_id}.json"
        if not override_path.exists():
            legacy_path = self.legacy_user_dir / f"{pack_id}.json"
            if legacy_path.exists():
                override_path = legacy_path

        return base_path, manifest_dict, script_path, override_path

    def load_pack(
        self, pack_id: str
    ) -> Tuple[LanguagePack, List[ValidationIssue]]:
        base_path, manifest_dict, script_path, override_path = self._resolve_pack_paths(pack_id)
        # Ghi tạm manifest_dict qua build_pack_from_dict hoặc file manifest
        from core.loader import build_pack_from_dict

        with open(base_path, "r", encoding="utf-8") as f:
            pack_data = json.load(f)
        script_data = None
        if script_path and script_path.exists():
            with open(script_path, "r", encoding="utf-8") as f:
                script_data = json.load(f)
        override_data = None
        if override_path and override_path.exists():
            with open(override_path, "r", encoding="utf-8") as f:
                override_data = json.load(f)

        pack, pack_issues = build_pack_from_dict(
            data=pack_data,
            override_data=override_data,
            script_data=script_data,
            manifest_data=manifest_dict,
        )
        self.packs[pack_id] = pack
        self.issues[pack_id] = pack_issues
        return pack, pack_issues

    def load_enabled_packs(self) -> Dict[str, LanguagePack]:
        self.discover_modes()
        if not self.settings:
            self.load_settings()
        self.packs.clear()
        self.issues.clear()
        for pack_id in self.settings.get("enabled_packs", []):
            if pack_id in self._mode_index or (self.packs_dir / pack_id).exists() or (self.packs_dir / "vi" / pack_id).exists():
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
        bindings: Optional[Any] = None,
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
        base_path, m_data, _, override_path = self._resolve_pack_paths(pack_id)
        with open(base_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if m_data:
            data.setdefault("meta", {})
            data["meta"]["id"] = m_data.get("id", pack_id)
            data["meta"]["name"] = m_data.get("name", pack_id)
            badge = m_data.get("badge", {})
            data["meta"]["symbol"] = badge.get("label", pack_id.upper()[:3]) if isinstance(badge, dict) else str(badge)
            data["badge"] = badge
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

    # --- Đồng bộ trạng thái & Tự khởi động ---

    @property
    def state_path(self) -> Path:
        return self.config_dir / "state.json"

    @property
    def autostart_path(self) -> Path:
        return Path.home() / ".config" / "autostart" / "multilingual-fasttype.desktop"

    def load_state(self) -> dict:
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
        self.ensure_config_dirs()
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False)

    def is_autostart_enabled(self) -> bool:
        return self.autostart_path.exists()

    def set_autostart(self, enabled: bool, _tray_script_path: Optional[Path] = None) -> None:
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