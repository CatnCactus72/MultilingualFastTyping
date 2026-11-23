#!/usr/bin/env python3
# ibus_frontend/main.py
from pathlib import Path
import subprocess
import sys
from typing import Dict, Optional, Set, Tuple

# Đảm bảo import được thư mục core/ khi IBus gọi trực tiếp script này
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, GObject, IBus

from core.engine import FastTypeEngine, KeyEvent, Passthrough, Replace, ResetEvent
from core.pack_manager import PackManager

# Tập các mã phím ngắt (Mục 4.2 - Bước 2)
BREAK_KEYVALS: Set[int] = {
    IBus.KEY_space,
    IBus.KEY_Return,
    IBus.KEY_KP_Enter,
    IBus.KEY_Tab,
    IBus.KEY_ISO_Left_Tab,
    IBus.KEY_Escape,
    IBus.KEY_BackSpace,
    IBus.KEY_Delete,
    IBus.KEY_KP_Delete,
    IBus.KEY_Home,
    IBus.KEY_End,
    IBus.KEY_Left,
    IBus.KEY_Up,
    IBus.KEY_Right,
    IBus.KEY_Down,
    IBus.KEY_Page_Up,
    IBus.KEY_Page_Down,
}

# Các phím Modifier đơn thuần (khi vừa nhấn xuống thì bỏ qua, không xóa buffer)
MODIFIER_KEYVALS: Set[int] = {
    IBus.KEY_Shift_L,
    IBus.KEY_Shift_R,
    IBus.KEY_Caps_Lock,
    IBus.KEY_Control_L,
    IBus.KEY_Control_R,
    IBus.KEY_Alt_L,
    IBus.KEY_Alt_R,
    IBus.KEY_Meta_L,
    IBus.KEY_Meta_R,
    IBus.KEY_Super_L,
    IBus.KEY_Super_R,
}

# Bảng tra cứu phím F1 -> F12
FN_KEYVALS: Dict[str, int] = {
    f"F{i}": getattr(IBus, f"KEY_F{i}") for i in range(1, 13)
}


def _normalize_mods(state: int) -> int:
  """Chỉ giữ lại đúng 4 bit: Ctrl (1), Shift (2), Alt (4), Super (8)."""
  mask = 0
  if state & IBus.ModifierType.CONTROL_MASK:
    mask |= 1
  if state & IBus.ModifierType.SHIFT_MASK:
    mask |= 2
  if state & IBus.ModifierType.MOD1_MASK:
    mask |= 4
  if state & IBus.ModifierType.SUPER_MASK:
    mask |= 8
  return mask


def parse_hotkey(hotkey_str: str) -> Optional[Tuple[int, str]]:
  """Chuyển chuỗi như 'Ctrl+Shift+F1' thành (norm_mod_mask, 'F1')."""
  parts = [p.strip() for p in hotkey_str.split("+") if p.strip()]
  if not parts:
    return None

  mod_mask = 0
  key_part = parts[-1].upper()

  for mod in parts[:-1]:
    m = mod.lower()
    if m in ("ctrl", "control"):
      mod_mask |= 1
    elif m == "shift":
      mod_mask |= 2
    elif m == "alt":
      mod_mask |= 4
    elif m in ("super", "win", "meta"):
      mod_mask |= 8

  return (mod_mask, key_part)

class FastTypeIBusEngine(IBus.Engine):
  __gtype_name__ = "FastTypeIBusEngine"

  _pack_manager = PackManager()
  _pack_manager.load_enabled_packs()
  _core = FastTypeEngine(None)
  _hotkey_map: Dict[Tuple[int, str], str] = {}
  _paused: bool = False
  _last_config_mtime: float = 0.0
  _last_state_mtime: float = 0.0

  @classmethod
  def _get_config_mtime(cls) -> float:
    mtimes = [0.0]
    if cls._pack_manager.settings_path.exists():
      mtimes.append(cls._pack_manager.settings_path.stat().st_mtime)
    if cls._pack_manager.overrides_dir.exists():
      for p in cls._pack_manager.overrides_dir.glob("*.json"):
        mtimes.append(p.stat().st_mtime)
    return max(mtimes)

  @classmethod
  def _get_state_mtime(cls) -> float:
    if cls._pack_manager.state_path.exists():
      return cls._pack_manager.state_path.stat().st_mtime
    return 0.0

  @classmethod
  def reload_configuration(cls) -> None:
    cls._pack_manager.load_settings()
    cls._pack_manager.load_enabled_packs()
    cls._hotkey_map.clear()
    hotkeys_cfg = cls._pack_manager.settings.get("hotkeys", {})
    for hk_str, pack_id in hotkeys_cfg.items():
      parsed = parse_hotkey(hk_str)
      if parsed is not None:
        cls._hotkey_map[parsed] = pack_id

    if cls._core.pack is not None:
      active_id = cls._core.pack.id
      cls._core.set_pack(cls._pack_manager.packs.get(active_id))
    cls._last_config_mtime = cls._get_config_mtime()

  @classmethod
  def reload_state_from_disk(cls) -> None:
    state = cls._pack_manager.load_state()
    cls._paused = bool(state.get("paused", False))
    pack_id = state.get("active_pack")
    if pack_id and pack_id in cls._pack_manager.packs:
      cls._core.set_pack(cls._pack_manager.packs[pack_id])
    else:
      cls._core.set_pack(None)
    cls._last_state_mtime = cls._get_state_mtime()

  @classmethod
  def save_state_to_disk(cls) -> None:
    active_id = cls._core.pack.id if cls._core.pack else None
    cls._pack_manager.save_state({
        "active_pack": active_id,
        "paused": cls._paused,
    })
    cls._last_state_mtime = cls._get_state_mtime()

  @classmethod
  def _check_sync(cls) -> None:
    if cls._get_config_mtime() > cls._last_config_mtime:
      cls.reload_configuration()
    if cls._get_state_mtime() > cls._last_state_mtime:
      cls.reload_state_from_disk()

  def __init__(self):
    super().__init__()
    self.prop_list = IBus.PropList()
    if not self._hotkey_map:
      self.reload_configuration()
      self.reload_state_from_disk()

  def do_enable(self) -> None:
    self.get_surrounding_text()
    self._core.reset()
    self._update_ibus_panel_properties()

  def do_disable(self) -> None:
    self._core.reset()

  def do_focus_in(self) -> None:
    self.get_surrounding_text()
    self._check_sync()
    self._core.process_event(ResetEvent())
    self._update_ibus_panel_properties()

  def do_focus_out(self) -> None:
    self._core.process_event(ResetEvent())

  def do_reset(self) -> None:
    self._core.process_event(ResetEvent())

  def do_property_activate(self, prop_name: str, prop_state: int) -> None:
    """Cho phép chọn ngôn ngữ / tạm dừng ngay trên menu IBus của GNOME Top Bar."""
    if prop_name == "Action.Pause":
      self._paused = not self._paused
      self._core.reset()
      self.save_state_to_disk()
      self._update_ibus_panel_properties()
    elif prop_name == "Pack.Default":
      self._paused = False
      self._core.set_pack(None)
      self.save_state_to_disk()
      self._update_ibus_panel_properties()
    elif prop_name.startswith("Pack."):
      pid = prop_name.split(".", 1)[1]
      if pid in self._pack_manager.packs:
        self._paused = False
        self._core.set_pack(self._pack_manager.packs[pid])
        self.save_state_to_disk()
        self._update_ibus_panel_properties()
    elif prop_name == "Action.Settings":
      settings_py = ROOT_DIR / "gui" / "settings_window.py"
      subprocess.Popen([sys.executable, str(settings_py)])

  def _update_ibus_panel_properties(self) -> None:
    """Hiển thị ký hiệu (FR/DE/ES/IT/EN) và menu ngay trên thanh IBus của hệ điều hành."""
    self.prop_list = IBus.PropList()
    if self._paused:
      symbol = "||"
      label_str = "Trạng thái: Đang tạm dừng (Click để tiếp tục)"
    elif self._core.pack is not None:
      symbol = self._core.pack.symbol
      label_str = f"Đang bật: [{symbol}] {self._core.pack.name}"
    else:
      symbol = "EN"
      label_str = "Đang bật: [EN] Bộ gõ mặc định"

    # Danh sách chọn nhanh trên menu IBus
    self.prop_list.append(
        IBus.Property.new(
            key="Pack.Default",
            type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("[EN] Bộ gõ mặc định"),
            icon="",
            tooltip=IBus.Text.new_from_string("Tắt biến đổi ký tự"),
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            prop_list=None,
        )
    )
    for pid in self._pack_manager.settings.get("enabled_packs", []):
      p = self._pack_manager.packs.get(pid)
      if p:
        self.prop_list.append(
            IBus.Property.new(
                key=f"Pack.{pid}",
                type=IBus.PropType.NORMAL,
                label=IBus.Text.new_from_string(f"[{p.symbol}] {p.name}"),
                icon="",
                tooltip=IBus.Text.new_from_string(f"Chuyển sang {p.name}"),
                sensitive=True,
                visible=True,
                state=IBus.PropState.UNCHECKED,
                prop_list=None,
            )
        )
    self.prop_list.append(
        IBus.Property.new(
            key="Action.Pause",
            type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string(label_str),
            icon="",
            tooltip=IBus.Text.new_from_string("Bật/Tắt tạm dừng ứng dụng"),
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            prop_list=None,
        )
    )
    self.prop_list.append(
        IBus.Property.new(
            key="Action.Settings",
            type=IBus.PropType.NORMAL,
            label=IBus.Text.new_from_string("Mở Cài đặt..."),
            icon="",
            tooltip=IBus.Text.new_from_string("Mở bảng chỉnh sửa quy tắc"),
            sensitive=True,
            visible=True,
            state=IBus.PropState.UNCHECKED,
            prop_list=None,
        )
    )
    self.register_properties(self.prop_list)

  def do_process_key_event(
      self, keyval: int, keycode: int, state: int
  ) -> bool:
    self._check_sync()

    # 1. Bỏ qua sự kiện nhả phím (Key Release)
    if state & IBus.ModifierType.RELEASE_MASK:
      return False

    # 2. Nếu ứng dụng đang ở chế độ Tạm dừng (FR-19): passthrough mọi phím
    if self._paused:
      return False

    if keyval in MODIFIER_KEYVALS:
      return False

    # 3. Kiểm tra tổ hợp phím tắt đổi gói ngôn ngữ (FR-05, FR-19)
    norm_mods = _normalize_mods(state)
    key_name = IBus.keyval_name(keyval) or ""
    key_name_upper = key_name.upper().replace("KP_", "")

    if (norm_mods, key_name_upper) in self._hotkey_map:
      target_pack_id = self._hotkey_map[(norm_mods, key_name_upper)]
      self._toggle_language_pack(target_pack_id)
      return True

    # 4. Phím kèm Ctrl / Alt / Super -> reset bộ đệm
    has_non_shift_mod = bool(
        state
        & (
            IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.SUPER_MASK
        )
    )
    if has_non_shift_mod:
      self._core.process_event(ResetEvent(reason="modifier"))
      return False

    # 5. Phím BackSpace -> để composer xử lý xóa theo ô (dời lại dấu thanh tiếng Việt nếu cần)
    if keyval == IBus.KEY_BackSpace:
      action = self._core.backspace()
      if isinstance(action, Replace):
        self._apply_replacement(action.delete_n, action.text)
        return True
      return False

    # Các phím ngắt khác (Space, Enter, Tab, Arrow...)
    if keyval in BREAK_KEYVALS:
      if keyval == IBus.KEY_space:
        # Gửi ký tự ' ' để tiếng Việt kích hoạt khôi phục từ sai (restore_invalid) nếu có
        action = self._core.process_event(KeyEvent(char=" ", keyval=keyval, is_upper=False, is_printable=True))
        if isinstance(action, Replace):
          self._apply_replacement(action.delete_n, action.text)
          return True
        return False
      self._core.process_event(ResetEvent(reason="break_key"))
      return False

    # 6. Chuyển mã phím IBus sang ký tự Unicode in được
    cp = IBus.keyval_to_unicode(keyval)
    if isinstance(cp, int):
      if cp == 0:
        self._core.process_event(ResetEvent(reason="non_printable"))
        return False
      ch = chr(cp)
    elif isinstance(cp, str):
      if not cp or cp == "\x00":
        self._core.process_event(ResetEvent(reason="non_printable"))
        return False
      ch = cp
    else:
      self._core.process_event(ResetEvent(reason="non_printable"))
      return False

    if not ch.isprintable():
      self._core.process_event(ResetEvent(reason="non_printable"))
      return False

    is_upper = ch.isupper()
    action = self._core.process_event(KeyEvent(char=ch, is_upper=is_upper))

    if isinstance(action, Passthrough):
      return False

    if isinstance(action, Replace):
      self._apply_replacement(action.delete_count, action.text)
      return action.consume_key

    return False

  def _apply_replacement(self, delete_count: int, text: str) -> None:
    if delete_count > 0:
      caps = getattr(self, "client_capabilities", 0)
      if caps & IBus.Capabilite.SURROUNDING_TEXT:
        self.delete_surrounding_text(-delete_count, delete_count)
      else:
        for _ in range(delete_count):
          self.forward_key_event(IBus.KEY_BackSpace, 14, 0)
          self.forward_key_event(
              IBus.KEY_BackSpace,
              14,
              int(IBus.ModifierType.RELEASE_MASK),
          )
    if text:
      self.commit_text(IBus.Text.new_from_string(text))

  def _toggle_language_pack(self, pack_id: str) -> None:
    current = self._core.pack
    if current is not None and current.id == pack_id:
      self._core.set_pack(None)
      self.save_state_to_disk()
      self._update_ibus_panel_properties()
      self._notify("Bộ gõ mặc định (EN)", "Đã tắt biến đổi ký tự")
      return

    pack = self._pack_manager.packs.get(pack_id)
    if pack is None:
      return
    self._core.set_pack(pack)
    self.save_state_to_disk()
    self._update_ibus_panel_properties()
    self._notify(f"[{pack.symbol}] {pack.name}", f"Đã bật gói {pack.name}")

  def _notify(self, title: str, body: str) -> None:
    if not self._pack_manager.settings.get("notifications", True):
      return
    try:
      subprocess.Popen(
          [
              "notify-send",
              "-a",
              "MultilingualFastType",
              "-t",
              "1200",
              "-h",
              "string:x-canonical-private-synchronous:fasttype-lang",
              title,
              body,
          ],
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )
    except FileNotFoundError:
      pass
    

class FastTypeApplication:

  def __init__(self, exec_by_ibus: bool):
    IBus.init()
    self.bus = IBus.Bus()
    self.bus.connect("disconnected", self._on_disconnected)
    self.factory = IBus.Factory.new(self.bus.get_connection())
    self.factory.add_engine(
        "multilingual-fasttype",
        GObject.type_from_name("FastTypeIBusEngine"),
    )
    if exec_by_ibus:
      self.bus.request_name("org.freedesktop.IBus.MultilingualFastType", 0)
    else:
      component = IBus.Component.new(
          "org.freedesktop.IBus.MultilingualFastType",
          "Multilingual FastType Input Method",
          "0.1.0",
          "MIT",
          "MultilingualFastType Dev",
          "https://localhost",
          "",
          "multilingual-fasttype",
      )
      engine_desc = IBus.EngineDesc.new(
          "multilingual-fasttype",
          "Multilingual FastType",
          "Gõ nhanh đa ngôn ngữ (FR, DE, ES, IT)",
          "other",
          "MIT",
          "MultilingualFastType Dev",
          "input-keyboard",
          "us",
      )
      component.add_engine(engine_desc)
      self.bus.register_component(component)

  def _on_disconnected(self, _bus) -> None:
    self.loop.quit()

  def run(self) -> None:
    self.loop = GLib.MainLoop()
    self.loop.run()


if __name__ == "__main__":
  exec_by_ibus = "--ibus" in sys.argv
  app = FastTypeApplication(exec_by_ibus=exec_by_ibus)
  app.run()