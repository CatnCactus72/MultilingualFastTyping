#!/usr/bin/env python3
# gui/tray_icon.py
from pathlib import Path
import subprocess
import sys
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

# Thử nạp AppIndicator3 (chuẩn khay hệ thống trên Ubuntu/GNOME/KDE)
INDICATOR_LIB = None
try:
  gi.require_version("AyatanaAppIndicator3", "0.1")
  from gi.repository import AyatanaAppIndicator3 as AppIndicator3

  INDICATOR_LIB = "ayatana"
except (ValueError, ImportError):
  try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

    INDICATOR_LIB = "legacy"
  except (ValueError, ImportError):
    INDICATOR_LIB = None

from core.pack_manager import PACK_COLORS, PackManager


def generate_badge_svg(icon_dir: Path, symbol: str, bg_color: str) -> Path:
  """Tạo file icon SVG vuông bo góc có màu riêng và ký hiệu 2 chữ (Mục 4.7)."""
  icon_dir.mkdir(parents=True, exist_ok=True)
  safe_name = symbol.replace("|", "P")
  svg_path = icon_dir / f"badge_{safe_name}.svg"
  svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect x="4" y="4" width="56" height="56" rx="12" ry="12" fill="{bg_color}"/>
  <text x="32" y="42" font-family="sans-serif" font-size="28" font-weight="bold"
        fill="#ffffff" text-anchor="middle">{symbol}</text>
</svg>
"""
  with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content)
  return svg_path


class FastTypeTray:

  def __init__(self):
    self.manager = PackManager()
    self.manager.load_settings()
    self.manager.load_enabled_packs()

    self.icon_dir = self.manager.config_dir / "icons"
    self._pregenerate_icons()

    self._last_state_mtime: float = 0.0
    self._last_config_mtime: float = 0.0
    self._updating_menu: bool = False

    self.menu = self._build_menu()

    if INDICATOR_LIB is not None:
      self.indicator = AppIndicator3.Indicator.new(
          "multilingual-fasttype-tray",
          str(self.icon_dir / "badge_EN.svg"),
          AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
      )
      self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
      self.indicator.set_menu(self.menu)
      self.status_icon = None
    else:
      # Fallback sang Gtk.StatusIcon nếu hệ thống chưa cài gir1.2-ayatanaappindicator3-0.1
      self.indicator = None
      self.status_icon = Gtk.StatusIcon()
      self.status_icon.set_from_file(str(self.icon_dir / "badge_EN.svg"))
      self.status_icon.connect("popup-menu", self._on_status_icon_popup)

    self._sync_from_disk(force=True)
    # Kiểm tra đồng bộ trạng thái mỗi 300ms
    GLib.timeout_add(300, self._poll_changes)

  def _pregenerate_icons(self) -> None:
    generate_badge_svg(self.icon_dir, "EN", PACK_COLORS["EN"])
    generate_badge_svg(self.icon_dir, "||", PACK_COLORS["PAUSED"])
    for pid, pack in self.manager.packs.items():
      color = PACK_COLORS.get(pid, "#1565c0")
      generate_badge_svg(self.icon_dir, pack.symbol, color)

  def _build_menu(self) -> Gtk.Menu:
    menu = Gtk.Menu()

    # 1. Bộ gõ mặc định (EN)
    self.item_default = Gtk.CheckMenuItem(label="[EN] Bộ gõ mặc định")
    self.item_default.connect("toggled", self._on_select_pack, None)
    menu.append(self.item_default)

    # 2. Danh sách các gói đang bật
    self.pack_items = {}
    for pid in self.manager.settings.get("enabled_packs", []):
      pack = self.manager.packs.get(pid)
      if not pack:
        continue
      item = Gtk.CheckMenuItem(label=f"[{pack.symbol}] {pack.name}")
      item.connect("toggled", self._on_select_pack, pid)
      menu.append(item)
      self.pack_items[pid] = item

    menu.append(Gtk.SeparatorMenuItem())

    # 3. Tạm dừng ứng dụng (FR-13, FR-19)
    self.item_pause = Gtk.CheckMenuItem(label="Tạm dừng ứng dụng (Pause)")
    self.item_pause.connect("toggled", self._on_toggle_pause)
    menu.append(self.item_pause)

    # 4. Tự khởi động cùng hệ thống (FR-14)
    self.item_autostart = Gtk.CheckMenuItem(label="Tự khởi động cùng hệ thống")
    self.item_autostart.set_active(self.manager.is_autostart_enabled())
    self.item_autostart.connect("toggled", self._on_toggle_autostart)
    menu.append(self.item_autostart)

    menu.append(Gtk.SeparatorMenuItem())

    # 5. Mở cài đặt (M3)
    item_settings = Gtk.MenuItem(label="Mở Cài đặt...")
    item_settings.connect("activate", self._on_open_settings)
    menu.append(item_settings)

    # 6. Thoát khay hệ thống
    item_quit = Gtk.MenuItem(label="Đóng biểu tượng khay")
    item_quit.connect("activate", lambda _: Gtk.main_quit())
    menu.append(item_quit)

    menu.show_all()
    return menu

  def _on_status_icon_popup(self, icon, button, activate_time) -> None:
    self.menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, activate_time)

  def _on_select_pack(self, widget: Gtk.CheckMenuItem, pack_id: Optional[str]) -> None:
    if self._updating_menu or not widget.get_active():
      return
    self.manager.save_state({"active_pack": pack_id, "paused": False})
    self._sync_from_disk(force=True)

  def _on_toggle_pause(self, widget: Gtk.CheckMenuItem) -> None:
    if self._updating_menu:
      return
    state = self.manager.load_state()
    state["paused"] = widget.get_active()
    self.manager.save_state(state)
    self._sync_from_disk(force=True)

  def _on_toggle_autostart(self, widget: Gtk.CheckMenuItem) -> None:
    if self._updating_menu:
      return
    self.manager.set_autostart(widget.get_active(), Path(__file__).resolve())

  def _on_open_settings(self, _widget) -> None:
    settings_py = ROOT_DIR / "gui" / "settings_window.py"
    subprocess.Popen([sys.executable, str(settings_py)])

  def _poll_changes(self) -> bool:
    cfg_mtime = (
        self.manager.settings_path.stat().st_mtime
        if self.manager.settings_path.exists()
        else 0.0
    )
    if cfg_mtime > self._last_config_mtime:
      self._last_config_mtime = cfg_mtime
      self.manager.load_settings()
      self.manager.load_enabled_packs()
      self._pregenerate_icons()
      self.menu = self._build_menu()
      if self.indicator is not None:
        self.indicator.set_menu(self.menu)
      self._sync_from_disk(force=True)

    self._sync_from_disk(force=False)
    return True

  def _sync_from_disk(self, force: bool = False) -> None:
    st_mtime = (
        self.manager.state_path.stat().st_mtime
        if self.manager.state_path.exists()
        else 0.0
    )
    if not force and st_mtime <= self._last_state_mtime:
      return
    self._last_state_mtime = st_mtime

    state = self.manager.load_state()
    active_pack = state.get("active_pack")
    paused = bool(state.get("paused", False))

    self._updating_menu = True
    try:
      self.item_pause.set_active(paused)
      self.item_default.set_active(not paused and active_pack is None)
      for pid, item in self.pack_items.items():
        item.set_active(not paused and active_pack == pid)
    finally:
      self._updating_menu = False

    if paused:
      icon_file = self.icon_dir / "badge_PP.svg"
      title = "Multilingual FastType: Đang tạm dừng"
    elif active_pack and active_pack in self.manager.packs:
      sym = self.manager.packs[active_pack].symbol
      icon_file = self.icon_dir / f"badge_{sym}.svg"
      title = f"Multilingual FastType: [{sym}]"
    else:
      icon_file = self.icon_dir / "badge_EN.svg"
      title = "Multilingual FastType: [EN]"

    if self.indicator is not None:
      self.indicator.set_icon_full(str(icon_file), title)
    elif self.status_icon is not None:
      self.status_icon.set_from_file(str(icon_file))
      self.status_icon.set_tooltip_text(title)


if __name__ == "__main__":
  tray = FastTypeTray()
  Gtk.main()