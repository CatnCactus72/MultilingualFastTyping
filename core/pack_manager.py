# core/pack_manager.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from core.loader import LanguagePack, ValidationIssue, load_pack_files

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "multilingual-fasttype"
DEFAULT_PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"

DEFAULT_SETTINGS = {
    "enabled_packs": ["fr", "de", "es", "it"],
    "hotkeys": {
        "Ctrl+Shift+F1": "fr",
        "Ctrl+Shift+F2": "de",
        "Ctrl+Shift+F3": "es",
        "Ctrl+Shift+F4": "it",
    },
    "notifications": True,
}

PACK_COLORS = {
    "EN": "#2e7d32",  # Xanh lá (Mặc định)
    "PAUSED": "#757575",  # Xám (Tạm dừng)
    "fr": "#1565c0",  # Xanh dương (Pháp)
    "de": "#000000",  # Cam đậm (Đức)
    "es": "#c62828",  # Đỏ (Tây Ban Nha)
    "it": "#00838f",  # Xanh ngọc (Ý)
}

class PackManager:

  def __init__(
      self,
      packs_dir: Path = DEFAULT_PACKS_DIR,
      config_dir: Path = DEFAULT_CONFIG_DIR,
  ):
    self.packs_dir = packs_dir
    self.config_dir = config_dir
    self.user_dir = self.config_dir / "user"
    self.settings_path = self.config_dir / "settings.json"
    self.packs: Dict[str, LanguagePack] = {}
    self.issues: Dict[str, List[ValidationIssue]] = {}
    self.settings: dict = {}

  def ensure_config_dirs(self) -> None:
    """Khởi tạo thư mục cấu hình và file settings.json mặc định nếu chưa có."""
    self.user_dir.mkdir(parents=True, exist_ok=True)
    if not self.settings_path.exists():
      with open(self.settings_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)

  def load_settings(self) -> dict:
    self.ensure_config_dirs()
    with open(self.settings_path, "r", encoding="utf-8") as f:
      self.settings = json.load(f)
    return self.settings

  def load_pack(
      self, pack_id: str
  ) -> Tuple[LanguagePack, List[ValidationIssue]]:
    base_path = self.packs_dir / f"{pack_id}.json"
    override_path = self.user_dir / f"{pack_id}.json"
    pack, pack_issues = load_pack_files(
        base_path, override_path if override_path.exists() else None
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
  ) -> Tuple[LanguagePack, List[ValidationIssue]]:
    """Lưu file ghi đè của người dùng (FR-18) sau khi kiểm tra không có lỗi xung đột."""
    self.ensure_config_dirs()
    override_data = {
        "rules": rules or {},
        "disable": disable or [],
        "upper": upper or {},
    }
    override_path = self.user_dir / f"{pack_id}.json"
    with open(override_path, "w", encoding="utf-8") as f:
      json.dump(override_data, f, indent=2, ensure_ascii=False)
    return self.load_pack(pack_id)

  def save_settings(self, settings_data: dict) -> None:
    """Lưu file settings.json (danh sách gói bật, phím tắt, thông báo)."""
    self.ensure_config_dirs()
    self.settings = settings_data
    with open(self.settings_path, "w", encoding="utf-8") as f:
      json.dump(self.settings, f, indent=2, ensure_ascii=False)

  def get_merged_pack_dict(self, pack_id: str) -> dict:
    """Trả về dữ liệu JSON đã gộp giữa gói gốc và file ghi đè để hiển thị lên GUI."""
    base_path = self.packs_dir / f"{pack_id}.json"
    with open(base_path, "r", encoding="utf-8") as f:
      data = json.load(f)

    override_path = self.user_dir / f"{pack_id}.json"
    if override_path.exists():
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
    return data

  def reset_user_override(
      self, pack_id: str
  ) -> Tuple[LanguagePack, List[ValidationIssue]]:
    """Xóa file ghi đè của người dùng để khôi phục gói về mặc định gốc."""
    override_path = self.user_dir / f"{pack_id}.json"
    if override_path.exists():
      override_path.unlink()
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
    """Lưu trạng thái để đồng bộ tức thời giữa IBus Engine và System Tray."""
    self.ensure_config_dirs()
    with open(self.state_path, "w", encoding="utf-8") as f:
      json.dump(state_data, f, ensure_ascii=False)

  def is_autostart_enabled(self) -> bool:
    return self.autostart_path.exists()

  def set_autostart(self, enabled: bool, tray_script_path: Path) -> None:
    """FR-14: Bật/tắt tự khởi động cùng hệ thống qua chuẩn XDG Autostart."""
    self.autostart_path.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
      content = (
          "[Desktop Entry]\n"
          "Type=Application\n"
          "Name=Multilingual FastType Tray\n"
          "Comment=Chỉ báo và điều khiển bộ gõ Multilingual FastType\n"
          f"Exec=/usr/bin/python3 {tray_script_path}\n"
          "Icon=input-keyboard\n"
          "Terminal=false\n"
          "Categories=Utility;\n"
          "X-GNOME-Autostart-enabled=true\n"
      )
      with open(self.autostart_path, "w", encoding="utf-8") as f:
        f.write(content)
    else:
      if self.autostart_path.exists():
        self.autostart_path.unlink()