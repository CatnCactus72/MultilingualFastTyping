#!/usr/bin/env python3
# gui/settings_window.py
import json
from pathlib import Path
import sys
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from core.loader import ValidationIssue, _expand_diacritics, validate_raw_rules
from core.pack_manager import PackManager

ALL_PACK_IDS = [("fr", "Français (FR)"), ("de", "Deutsch (DE)"), ("es", "Español (ES)"), ("it", "Italiano (IT)")]


class SettingsWindow(Gtk.Window):

  def __init__(self):
    super().__init__(title="Multilingual FastType — Cài đặt (M3)")
    self.set_default_size(760, 560)
    self.set_border_width(12)

    self.manager = PackManager()
    self.manager.load_settings()
    self.manager.load_enabled_packs()

    self.current_pack_id = "fr"
    self.current_base_data: dict = {}

    notebook = Gtk.Notebook()
    self.add(notebook)

    # Tab 1: Sửa quy tắc & Kiểm tra xung đột (FR-10, FR-16, FR-18)
    notebook.append_page(
        self._build_rules_tab(), Gtk.Label(label="Bảng quy tắc & Dấu")
    )

    # Tab 2: Bật/tắt gói & Phím tắt (FR-09, FR-11)
    notebook.append_page(
        self._build_general_tab(), Gtk.Label(label="Gói ngôn ngữ & Phím tắt")
    )

    self._load_pack_into_ui("fr")

  # ================= TAB 1: BẢNG QUY TẮC & DẤU =================
  def _build_rules_tab(self) -> Gtk.Widget:
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    vbox.set_border_width(8)

    # Thanh chọn ngôn ngữ
    top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    top_bar.pack_start(Gtk.Label(label="Chọn gói ngôn ngữ:"), False, False, 0)

    self.pack_combo = Gtk.ComboBoxText()
    for pid, label in ALL_PACK_IDS:
      self.pack_combo.append(pid, label)
    self.pack_combo.set_active_id("fr")
    self.pack_combo.connect("changed", self._on_pack_changed)
    top_bar.pack_start(self.pack_combo, False, False, 0)

    btn_reset = Gtk.Button(label="Khôi phục mặc định gốc")
    btn_reset.connect("clicked", self._on_reset_pack)
    top_bar.pack_end(btn_reset, False, False, 0)
    vbox.pack_start(top_bar, False, False, 0)

    # Khung chia đôi: Nhóm dấu (Diacritics) ở trên, Quy tắc rời (Rules) ở dưới
    paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
    vbox.pack_start(paned, True, True, 0)

    # --- Phần A: Bảng Nhóm dấu (Diacritics kiểu VNI) ---
    frame_dia = Gtk.Frame(
        label=" 1. Nhóm dấu kết hợp (Sửa phím dấu áp dụng cho cả nhóm chữ cái) "
    )
    box_dia = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box_dia.set_border_width(6)

    # Cột: Tên dấu | Mã Unicode ẩn | Phím kích hoạt (phân cách bằng phẩy) | Các chữ cái áp dụng
    self.dia_store = Gtk.ListStore(str, str, str, str)
    dia_tree = Gtk.TreeView(model=self.dia_store)

    col_name = Gtk.TreeViewColumn("Loại dấu", Gtk.CellRendererText(), text=0)
    dia_tree.append_column(col_name)

    rend_trig = Gtk.CellRendererText(editable=True)
    rend_trig.connect("edited", self._on_dia_cell_edited, 2)
    col_trig = Gtk.TreeViewColumn(
        "Phím gõ dấu (click để sửa)", rend_trig, text=2
    )
    dia_tree.append_column(col_trig)

    rend_bases = Gtk.CellRendererText(editable=True)
    rend_bases.connect("edited", self._on_dia_cell_edited, 3)
    col_bases = Gtk.TreeViewColumn(
        "Chữ cái gốc áp dụng (cách nhau dấu phẩy)", rend_bases, text=3
    )
    dia_tree.append_column(col_bases)

    scroll_dia = Gtk.ScrolledWindow()
    scroll_dia.set_min_content_height(130)
    scroll_dia.add(dia_tree)
    box_dia.pack_start(scroll_dia, True, True, 0)
    frame_dia.add(box_dia)
    paned.pack1(frame_dia, resize=True, shrink=False)

    # --- Phần B: Bảng Quy tắc rời (Rules) ---
    frame_rules = Gtk.Frame(label=" 2. Quy tắc ký tự riêng lẻ (Cách gõ → Đầu ra) ")
    box_rules = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box_rules.set_border_width(6)

    self.rule_store = Gtk.ListStore(str, str)  # Đầu ra | Trigger (cách nhau phẩy)
    self.rule_tree = Gtk.TreeView(model=self.rule_store)

    rend_out = Gtk.CellRendererText(editable=True)
    rend_out.connect("edited", self._on_rule_cell_edited, 0)
    col_out = Gtk.TreeViewColumn("Ký tự đầu ra", rend_out, text=0)
    self.rule_tree.append_column(col_out)

    rend_rtrig = Gtk.CellRendererText(editable=True)
    rend_rtrig.connect("edited", self._on_rule_cell_edited, 1)
    col_rtrig = Gtk.TreeViewColumn(
        "Trigger / Cách gõ (cách nhau dấu phẩy)", rend_rtrig, text=1
    )
    self.rule_tree.append_column(col_rtrig)

    scroll_rules = Gtk.ScrolledWindow()
    scroll_rules.set_min_content_height(140)
    scroll_rules.add(self.rule_tree)
    box_rules.pack_start(scroll_rules, True, True, 0)

    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    btn_add = Gtk.Button(label="+ Thêm quy tắc")
    btn_add.connect("clicked", self._on_add_rule)
    btn_del = Gtk.Button(label="- Xóa quy tắc đang chọn")
    btn_del.connect("clicked", self._on_delete_rule)
    btn_box.pack_start(btn_add, False, False, 0)
    btn_box.pack_start(btn_del, False, False, 0)
    box_rules.pack_start(btn_box, False, False, 0)

    frame_rules.add(box_rules)
    paned.pack2(frame_rules, resize=True, shrink=False)

    # Khu vực hiển thị cảnh báo / lỗi xung đột trực tiếp (FR-16)
    self.status_label = Gtk.Label()
    self.status_label.set_xalign(0.0)
    self.status_label.set_line_wrap(True)
    vbox.pack_start(self.status_label, False, False, 4)

    # Nút Lưu gói
    bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    self.btn_save_pack = Gtk.Button(label="Lưu thay đổi cho gói này")
    self.btn_save_pack.get_style_context().add_class("suggested-action")
    self.btn_save_pack.connect("clicked", self._on_save_pack)
    bottom_bar.pack_end(self.btn_save_pack, False, False, 0)
    vbox.pack_start(bottom_bar, False, False, 0)

    return vbox

  # ================= TAB 2: GÓI NGÔN NGỮ & PHÍM TẮT =================
  def _build_general_tab(self) -> Gtk.Widget:
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    vbox.set_border_width(12)

    grid = Gtk.Grid(column_spacing=16, row_spacing=10)
    grid.attach(Gtk.Label(label="<b>Gói ngôn ngữ</b>", use_markup=True), 0, 0, 1, 1)
    grid.attach(Gtk.Label(label="<b>Bật chuyển nhanh</b>", use_markup=True), 1, 0, 1, 1)
    grid.attach(
        Gtk.Label(label="<b>Phím tắt (VD: Ctrl+Shift+F1)</b>", use_markup=True),
        2,
        0,
        1,
        1,
    )

    enabled_list = self.manager.settings.get("enabled_packs", [])
    hotkeys_cfg = self.manager.settings.get("hotkeys", {})
    pack_to_hk = {v: k for k, v in hotkeys_cfg.items()}

    self.pack_checks: Dict[str, Gtk.CheckButton] = {}
    self.hotkey_entries: Dict[str, Gtk.Entry] = {}

    for row_idx, (pid, label) in enumerate(ALL_PACK_IDS, start=1):
      lbl = Gtk.Label(label=label, xalign=0.0)
      chk = Gtk.CheckButton()
      chk.set_active(pid in enabled_list)
      entry = Gtk.Entry()
      entry.set_text(pack_to_hk.get(pid, ""))

      grid.attach(lbl, 0, row_idx, 1, 1)
      grid.attach(chk, 1, row_idx, 1, 1)
      grid.attach(entry, 2, row_idx, 1, 1)

      self.pack_checks[pid] = chk
      self.hotkey_entries[pid] = entry

    vbox.pack_start(grid, False, False, 0)

    self.chk_notify = Gtk.CheckButton(
        label="Hiện thông báo góc màn hình (notify-send) khi chuyển ngôn ngữ"
    )
    self.chk_notify.set_active(self.manager.settings.get("notifications", True))
    vbox.pack_start(self.chk_notify, False, False, 8)

    btn_save_gen = Gtk.Button(label="Lưu cài đặt chung & Phím tắt")
    btn_save_gen.connect("clicked", self._on_save_general)
    vbox.pack_start(btn_save_gen, False, False, 0)

    self.gen_status_label = Gtk.Label(label="")
    self.gen_status_label.set_xalign(0.0)
    vbox.pack_start(self.gen_status_label, False, False, 0)

    return vbox

  # ================= XỬ LÝ SỰ KIỆN & KIỂM TRA XUNG ĐỘT =================
  def _load_pack_into_ui(self, pack_id: str) -> None:
    self.current_pack_id = pack_id
    with open(self.manager.packs_dir / f"{pack_id}.json", "r", encoding="utf-8") as f:
      self.current_base_data = json.load(f)

    merged = self.manager.get_merged_pack_dict(pack_id)

    self.dia_store.clear()
    for d in merged.get("diacritics", []):
      trigs = ", ".join(d.get("triggers", []))
      bases = ", ".join(d.get("bases", []))
      self.dia_store.append([d.get("name", ""), d.get("combining", ""), trigs, bases])

    self.rule_store.clear()
    for out, trigs in merged.get("rules", {}).items():
      t_list = [trigs] if isinstance(trigs, str) else trigs
      self.rule_store.append([out, ", ".join(t_list)])

    self._validate_current_ui()

  def _on_pack_changed(self, combo: Gtk.ComboBoxText) -> None:
    pid = combo.get_active_id()
    if pid:
      self._load_pack_into_ui(pid)

  def _on_dia_cell_edited(self, _widget, path, new_text: str, col: int) -> None:
    self.dia_store[path][col] = new_text.strip()
    self._validate_current_ui()

  def _on_rule_cell_edited(self, _widget, path, new_text: str, col: int) -> None:
    self.rule_store[path][col] = new_text.strip()
    self._validate_current_ui()

  def _on_add_rule(self, _btn) -> None:
    self.rule_store.append(["", ""])
    self._validate_current_ui()

  def _on_delete_rule(self, _btn) -> None:
    sel = self.rule_tree.get_selection()
    model, treeiter = sel.get_selected()
    if treeiter is not None:
      model.remove(treeiter)
      self._validate_current_ui()

  def _collect_ui_data(self) -> tuple[List[dict], Dict[str, List[str]]]:
    diacritics_list: List[dict] = []
    for row in self.dia_store:
      name, combining, trigs_str, bases_str = row[0], row[1], row[2], row[3]
      trigs = [t.strip() for t in trigs_str.split(",") if t.strip()]
      bases = [b.strip() for b in bases_str.split(",") if b.strip()]
      diacritics_list.append({
          "name": name,
          "combining": combining,
          "triggers": trigs,
          "bases": bases,
      })

    rules_dict: Dict[str, List[str]] = {}
    for row in self.rule_store:
      out, trigs_str = row[0].strip(), row[1].strip()
      trigs = [t.strip() for t in trigs_str.split(",") if t.strip()]
      if out in rules_dict:
        # Gộp nếu người dùng nhập 2 dòng cùng ký tự đầu ra
        rules_dict[out].extend(trigs)
      else:
        rules_dict[out] = trigs if trigs else [""]

    return diacritics_list, rules_dict

  def _validate_current_ui(self) -> List[ValidationIssue]:
    diacritics_list, rules_dict = self._collect_ui_data()
    combined_rules: Dict[str, List[str]] = {}
    _expand_diacritics(diacritics_list, combined_rules)
    for out, trigs in rules_dict.items():
      if out in combined_rules:
        combined_rules[out].extend(trigs)
      else:
        combined_rules[out] = list(trigs)

    issues = validate_raw_rules(combined_rules)
    errors = [i for i in issues if i.level == "ERROR"]
    warnings = [i for i in issues if i.level == "WARNING"]

    if errors:
      msg = "<b><span foreground='#d32f2f'>LỖI (Không thể lưu):</span></b>\n" + "\n".join(
          f"• {e.message}" for e in errors
      )
      self.status_label.set_markup(msg)
      self.btn_save_pack.set_sensitive(False)
    elif warnings:
      msg = "<b><span foreground='#f57c00'>CẢNH BÁO (Vẫn cho phép lưu):</span></b>\n" + "\n".join(
          f"• {w.message}" for w in warnings
      )
      self.status_label.set_markup(msg)
      self.btn_save_pack.set_sensitive(True)
    else:
      self.status_label.set_markup(
          "<b><span foreground='#388e3c'>✓ Bộ quy tắc hợp lệ, không có xung đột.</span></b>"
      )
      self.btn_save_pack.set_sensitive(True)

    return issues

  def _on_save_pack(self, _btn) -> None:
    diacritics_list, rules_dict = self._collect_ui_data()
    base_rules = self.current_base_data.get("rules", {})
    disabled = [out for out in base_rules if out not in rules_dict]

    override_data = {
        "diacritics": diacritics_list,
        "rules": rules_dict,
        "disable": disabled,
        "upper": self.current_base_data.get("upper", {}),
    }
    self.manager.ensure_config_dirs()
    override_path = self.manager.user_dir / f"{self.current_pack_id}.json"
    with open(override_path, "w", encoding="utf-8") as f:
      json.dump(override_data, f, indent=2, ensure_ascii=False)

    self.manager.load_pack(self.current_pack_id)
    self.status_label.set_markup(
        f"<b><span foreground='#1976d2'>✓ Đã lưu vào {override_path} (IBus sẽ tự động cập nhật).</span></b>"
    )

  def _on_reset_pack(self, _btn) -> None:
    self.manager.reset_user_override(self.current_pack_id)
    self._load_pack_into_ui(self.current_pack_id)
    self.status_label.set_markup(
        "<b><span foreground='#1976d2'>✓ Đã khôi phục gói về mặc định gốc.</span></b>"
    )

  def _on_save_general(self, _btn) -> None:
    enabled = [pid for pid, chk in self.pack_checks.items() if chk.get_active()]
    hotkeys: Dict[str, str] = {}
    seen_hk: Dict[str, str] = {}

    for pid, entry in self.hotkey_entries.items():
      hk = entry.get_text().strip()
      if not hk:
        continue
      hk_norm = hk.upper()
      if hk_norm in seen_hk:
        self.gen_status_label.set_markup(
            f"<b><span foreground='#d32f2f'>Lỗi: Trùng phím tắt '{hk}' giữa gói {seen_hk[hk_norm]} và {pid}!</span></b>"
        )
        return
      seen_hk[hk_norm] = pid
      hotkeys[hk] = pid

    new_settings = {
        "enabled_packs": enabled,
        "hotkeys": hotkeys,
        "notifications": self.chk_notify.get_active(),
    }
    self.manager.save_settings(new_settings)
    self.gen_status_label.set_markup(
        "<b><span foreground='#388e3c'>✓ Đã lưu cài đặt chung và phím tắt!</span></b>"
    )


if __name__ == "__main__":
  win = SettingsWindow()
  win.connect("destroy", Gtk.main_quit)
  win.show_all()
  Gtk.main()