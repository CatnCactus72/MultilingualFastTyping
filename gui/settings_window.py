#!/usr/bin/env python3
# gui/settings_window.py
import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.conflicts.framework import ValidationIssue
from core.conflicts.generic_rules import validate_generic_rules
from core.loader import expand_diacritics_to_rules
from core.pack_manager import PackManager

ALL_PACK_IDS = [
    ("fr", "Français (FRA)"),
    ("de", "Deutsch (DEU)"),
    ("es", "Español (ESP)"),
    ("it", "Italiano (ITA)"),
    ("vi_vni", "Tiếng Việt VNI (VNI)"),
    ("vi_telex", "Tiếng Việt Telex (TLX)"),
    ("zh_pinyin", "Pinyin dấu thanh (PIN)"),
    ("ru", "Русский — Tiếng Nga (RUS)"),
    ("ja_hiragana", "日本語 — Hiragana (JPN)"),
]

VI_OP_LABELS = [
    ("TONE_SAC", "Dấu Sắc (á)"),
    ("TONE_HUYEN", "Dấu Huyền (à)"),
    ("TONE_HOI", "Dấu Hỏi (ả)"),
    ("TONE_NGA", "Dấu Ngã (ã)"),
    ("TONE_NANG", "Dấu Nặng (ạ)"),
    ("TONE_CLEAR", "Xóa dấu thanh"),
    ("MARK_CIRC", "Dấu Mũ (â, ê, ô)"),
    ("MARK_HORN", "Dấu Móc (ơ, ư)"),
    ("MARK_BREVE", "Dấu Trăng (ă)"),
    ("STROKE_D", "Gạch ngang (đ)"),
]

PINYIN_OP_LABELS = [
    ("TONE_1", "Thanh 1 — Ngang (ā)"),
    ("TONE_2", "Thanh 2 — Sắc (á)"),
    ("TONE_3", "Thanh 3 — Hỏi/Trắc (ǎ)"),
    ("TONE_4", "Thanh 4 — Huyền (à)"),
    ("TONE_CLEAR", "Xóa dấu thanh (a)"),
    ("MARK_DIAERESIS", "Dấu hai chấm trên u (ü)"),
]


class SettingsWindow(Gtk.Window):

    def __init__(self):
        super().__init__(title="Multilingual FastType — Cài đặt")
        self.set_default_size(780, 580)
        self.set_border_width(12)

        self.manager = PackManager()
        self.manager.load_settings()
        self.manager.load_enabled_packs()

        self.current_pack_id = "fr"
        self.current_base_data: dict = {}

        notebook = Gtk.Notebook()
        self.add(notebook)

        notebook.append_page(
            self._build_rules_tab(), Gtk.Label(label="Bảng quy tắc & Dấu")
        )
        notebook.append_page(
            self._build_general_tab(), Gtk.Label(label="Gói ngôn ngữ & Phím tắt")
        )

        self._load_pack_into_ui("fr")

    # ================= TAB 1: BẢNG QUY TẮC & DẤU =================
    def _build_rules_tab(self) -> Gtk.Widget:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_border_width(8)

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

        self.editor_stack = Gtk.Stack()
        vbox.pack_start(self.editor_stack, True, True, 0)

        # --- Trang 1: Giao diện cho GĐ1 (FRA, DEU, ESP, ITA) ---
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)

        frame_dia = Gtk.Frame(label=" 1. Nhóm dấu kết hợp (Áp dụng cho cả nhóm chữ cái) ")
        box_dia = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box_dia.set_border_width(6)

        self.dia_store = Gtk.ListStore(str, str, str, str)
        dia_tree = Gtk.TreeView(model=self.dia_store)
        dia_tree.append_column(Gtk.TreeViewColumn("Loại dấu", Gtk.CellRendererText(), text=0))

        rend_trig = Gtk.CellRendererText(editable=True)
        rend_trig.connect("edited", self._on_dia_cell_edited, 2)
        dia_tree.append_column(
            Gtk.TreeViewColumn("Phím gõ dấu (click để sửa)", rend_trig, text=2)
        )

        rend_bases = Gtk.CellRendererText(editable=True)
        rend_bases.connect("edited", self._on_dia_cell_edited, 3)
        dia_tree.append_column(
            Gtk.TreeViewColumn("Chữ cái gốc (cách nhau dấu phẩy)", rend_bases, text=3)
        )

        scroll_dia = Gtk.ScrolledWindow()
        scroll_dia.set_min_content_height(130)
        scroll_dia.add(dia_tree)
        box_dia.pack_start(scroll_dia, True, True, 0)
        frame_dia.add(box_dia)
        paned.pack1(frame_dia, resize=True, shrink=False)

        frame_rules = Gtk.Frame(label=" 2. Quy tắc ký tự riêng lẻ (Cách gõ → Đầu ra) ")
        box_rules = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box_rules.set_border_width(6)

        self.rule_store = Gtk.ListStore(str, str)
        self.rule_tree = Gtk.TreeView(model=self.rule_store)

        rend_out = Gtk.CellRendererText(editable=True)
        rend_out.connect("edited", self._on_rule_cell_edited, 0)
        self.rule_tree.append_column(Gtk.TreeViewColumn("Ký tự đầu ra", rend_out, text=0))

        rend_rtrig = Gtk.CellRendererText(editable=True)
        rend_rtrig.connect("edited", self._on_rule_cell_edited, 1)
        self.rule_tree.append_column(
            Gtk.TreeViewColumn("Trigger / Cách gõ (cách nhau dấu phẩy)", rend_rtrig, text=1)
        )

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
        self.editor_stack.add_named(paned, "mapping")

        # --- Trang 2: Giao diện cho Tiếng Việt (VNI / Telex) ---
        vi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        opt_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        opt_bar.pack_start(Gtk.Label(label="Kiểu đặt dấu thanh:"), False, False, 0)
        self.vi_tone_combo = Gtk.ComboBoxText()
        self.vi_tone_combo.append("modern", "Kiểu mới (hòa, thủy)")
        self.vi_tone_combo.append("classic", "Kiểu cũ (hoà, thuỷ)")
        self.vi_tone_combo.set_active_id("modern")
        opt_bar.pack_start(self.vi_tone_combo, False, False, 0)

        self.vi_restore_chk = Gtk.CheckButton(label="Tự khôi phục từ sai khi nhấn Space/dấu câu")
        self.vi_restore_chk.set_active(True)
        opt_bar.pack_start(self.vi_restore_chk, False, False, 0)
        vi_box.pack_start(opt_bar, False, False, 0)

        frame_vi = Gtk.Frame(label=" Bảng gán phím 10 phép toán Tiếng Việt (Click vào cột phím để sửa) ")
        self.vi_store = Gtk.ListStore(str, str, str)
        vi_tree = Gtk.TreeView(model=self.vi_store)
        vi_tree.append_column(Gtk.TreeViewColumn("Phép toán dấu", Gtk.CellRendererText(), text=1))

        rend_vi_key = Gtk.CellRendererText(editable=True)
        rend_vi_key.connect("edited", self._on_vi_cell_edited)
        vi_tree.append_column(Gtk.TreeViewColumn("Phím gõ (cách nhau dấu phẩy)", rend_vi_key, text=2))

        scroll_vi = Gtk.ScrolledWindow()
        scroll_vi.set_min_content_height(260)
        scroll_vi.add(vi_tree)
        frame_vi.add(scroll_vi)
        vi_box.pack_start(frame_vi, True, True, 0)
        self.editor_stack.add_named(vi_box, "vietnamese")

        # --- Trang 3: Giao diện cho Pinyin dấu thanh (zh_pinyin) ---
        pin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        pin_opt_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.pin_v_umlaut_chk = Gtk.CheckButton(label="Dùng phím 'v' thay cho 'ü' (vd: nv3 → nǚ)")
        self.pin_v_umlaut_chk.set_active(True)
        pin_opt_bar.pack_start(self.pin_v_umlaut_chk, False, False, 0)

        self.pin_restore_chk = Gtk.CheckButton(label="Tự khôi phục từ sai khi nhấn Space/dấu câu")
        self.pin_restore_chk.set_active(True)
        pin_opt_bar.pack_start(self.pin_restore_chk, False, False, 0)
        pin_box.pack_start(pin_opt_bar, False, False, 0)

        frame_pin = Gtk.Frame(label=" Bảng gán phím thanh điệu & dấu Pinyin (Click vào cột phím để sửa) ")
        self.pin_store = Gtk.ListStore(str, str, str)
        pin_tree = Gtk.TreeView(model=self.pin_store)
        pin_tree.append_column(Gtk.TreeViewColumn("Thanh / Dấu Pinyin", Gtk.CellRendererText(), text=1))

        rend_pin_key = Gtk.CellRendererText(editable=True)
        rend_pin_key.connect("edited", self._on_pin_cell_edited)
        pin_tree.append_column(Gtk.TreeViewColumn("Phím gõ (cách nhau dấu phẩy)", rend_pin_key, text=2))

        scroll_pin = Gtk.ScrolledWindow()
        scroll_pin.set_min_content_height(260)
        scroll_pin.add(pin_tree)
        frame_pin.add(scroll_pin)
        pin_box.pack_start(frame_pin, True, True, 0)
        self.editor_stack.add_named(pin_box, "pinyin")

        # --- Trang 4: Giao diện cho GĐ3 (Tiếng Nga ru & Tiếng Nhật ja_hiragana) ---
        tr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Thanh tùy chọn động theo từng ngôn ngữ GĐ3
        self.tr_opt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Tùy chọn riêng của Tiếng Nga: phím dấu trọng âm
        self.ru_stress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ru_stress_box.pack_start(Gtk.Label(label="Phím dấu trọng âm (о́):"), False, False, 0)
        self.ru_stress_entry = Gtk.Entry()
        self.ru_stress_entry.set_width_chars(4)
        self.ru_stress_entry.set_max_length(1)
        self.ru_stress_box.pack_start(self.ru_stress_entry, False, False, 0)
        self.tr_opt_box.pack_start(self.ru_stress_box, False, False, 0)

        # Tùy chọn riêng của Tiếng Nhật: gấp đôi phụ âm (sokuon)
        self.ja_sokuon_chk = Gtk.CheckButton(label="Gấp đôi phụ âm tạo xúc âm っ (vd: kka → っか)")
        self.tr_opt_box.pack_start(self.ja_sokuon_chk, False, False, 0)

        tr_box.pack_start(self.tr_opt_box, False, False, 0)

        frame_tr = Gtk.Frame(label=" Bảng ánh xạ chuyển tự (Ký tự đích ↔ Chuỗi phím Latin) ")
        box_tr_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box_tr_inner.set_border_width(6)

        self.tr_store = Gtk.ListStore(str, str)
        self.tr_tree = Gtk.TreeView(model=self.tr_store)

        rend_tr_out = Gtk.CellRendererText(editable=True)
        rend_tr_out.connect("edited", self._on_tr_cell_edited, 0)
        self.tr_tree.append_column(Gtk.TreeViewColumn("Ký tự đích", rend_tr_out, text=0))

        rend_tr_trig = Gtk.CellRendererText(editable=True)
        rend_tr_trig.connect("edited", self._on_tr_cell_edited, 1)
        self.tr_tree.append_column(
            Gtk.TreeViewColumn("Chuỗi phím Latin (cách nhau dấu phẩy)", rend_tr_trig, text=1)
        )

        scroll_tr = Gtk.ScrolledWindow()
        scroll_tr.set_min_content_height(240)
        scroll_tr.add(self.tr_tree)
        box_tr_inner.pack_start(scroll_tr, True, True, 0)

        tr_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_tr_add = Gtk.Button(label="+ Thêm quy tắc")
        btn_tr_add.connect("clicked", self._on_add_tr_rule)
        btn_tr_del = Gtk.Button(label="- Xóa quy tắc đang chọn")
        btn_tr_del.connect("clicked", self._on_delete_tr_rule)
        tr_btn_box.pack_start(btn_tr_add, False, False, 0)
        tr_btn_box.pack_start(btn_tr_del, False, False, 0)
        box_tr_inner.pack_start(tr_btn_box, False, False, 0)

        frame_tr.add(box_tr_inner)
        tr_box.pack_start(frame_tr, True, True, 0)
        self.editor_stack.add_named(tr_box, "translit")

        # Khu vực báo trạng thái / lỗi
        self.status_label = Gtk.Label()
        self.status_label.set_xalign(0.0)
        self.status_label.set_line_wrap(True)
        vbox.pack_start(self.status_label, False, False, 4)

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

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(320)

        grid = Gtk.Grid(column_spacing=16, row_spacing=10)
        grid.attach(Gtk.Label(label="<b>Gói ngôn ngữ</b>", use_markup=True), 0, 0, 1, 1)
        grid.attach(Gtk.Label(label="<b>Bật chuyển nhanh</b>", use_markup=True), 1, 0, 1, 1)
        grid.attach(
            Gtk.Label(label="<b>Phím tắt (VD: Ctrl+Shift+F1)</b>", use_markup=True),
            2, 0, 1, 1,
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

        scrolled.add(grid)
        vbox.pack_start(scrolled, True, True, 0)

        self.chk_notify = Gtk.CheckButton(
            label="Hiện thông báo góc màn hình (notify-send) khi chuyển ngôn ngữ"
        )
        self.chk_notify.set_active(self.manager.settings.get("notifications", True))
        vbox.pack_start(self.chk_notify, False, False, 4)

        btn_save_gen = Gtk.Button(label="Lưu cài đặt chung & Phím tắt")
        btn_save_gen.connect("clicked", self._on_save_general)
        vbox.pack_start(btn_save_gen, False, False, 0)

        self.gen_status_label = Gtk.Label(label="")
        self.gen_status_label.set_xalign(0.0)
        vbox.pack_start(self.gen_status_label, False, False, 0)

        return vbox

    # ================= PHÂN LOẠI & NẠP DỮ LIỆU =================
    def _pack_category(self, pack_id: str) -> str:
        if pack_id.startswith("vi_"):
            return "vietnamese"
        if pack_id == "zh_pinyin":
            return "pinyin"
        if pack_id in ("ru", "ja_hiragana"):
            return "translit"
        return "mapping"

    def _load_pack_into_ui(self, pack_id: str) -> None:
        self.current_pack_id = pack_id
        base_path, _, _, _ = self.manager._resolve_pack_paths(pack_id)
        with open(base_path, "r", encoding="utf-8") as f:
            self.current_base_data = json.load(f)

        merged = self.manager.get_merged_pack_dict(pack_id)
        cat = self._pack_category(pack_id)

        if cat == "vietnamese":
            self.editor_stack.set_visible_child_name("vietnamese")
            opts = merged.get("options", {})
            self.vi_tone_combo.set_active_id(opts.get("tone_style", "modern"))
            self.vi_restore_chk.set_active(bool(opts.get("restore_invalid", True)))

            bindings = merged.get("bindings", {})
            op_to_keys: Dict[str, str] = {}
            if isinstance(bindings, dict):
                for op, val in bindings.items():
                    op_to_keys[op] = ", ".join(val) if isinstance(val, list) else str(val)

            self.vi_store.clear()
            for op_code, op_label in VI_OP_LABELS:
                self.vi_store.append([op_code, op_label, op_to_keys.get(op_code, "")])

            self._validate_current_ui()
            return

        if cat == "pinyin":
            self.editor_stack.set_visible_child_name("pinyin")
            opts = merged.get("options", {})
            self.pin_v_umlaut_chk.set_active(bool(opts.get("v_as_umlaut", True)))
            self.pin_restore_chk.set_active(bool(opts.get("restore_invalid", True)))

            bindings = merged.get("bindings", {})
            op_to_keys = {}
            if isinstance(bindings, dict):
                for op, val in bindings.items():
                    op_to_keys[op] = ", ".join(val) if isinstance(val, list) else str(val)

            self.pin_store.clear()
            for op_code, op_label in PINYIN_OP_LABELS:
                self.pin_store.append([op_code, op_label, op_to_keys.get(op_code, "")])

            self._validate_current_ui()
            return

        if cat == "translit":
            self.editor_stack.set_visible_child_name("translit")
            opts = merged.get("options", {})

            if pack_id == "ru":
                self.ru_stress_box.show_all()
                self.ja_sokuon_chk.hide()
                marks = opts.get("combining_marks", {})
                stress_key = next(iter(marks.keys()), "'") if isinstance(marks, dict) else "'"
                self.ru_stress_entry.set_text(stress_key)
            else:
                self.ru_stress_box.hide()
                self.ja_sokuon_chk.show()
                self.ja_sokuon_chk.set_active(bool(opts.get("double_consonant_sokuon", True)))

            self.tr_store.clear()
            for out, trigs in merged.get("rules", {}).items():
                t_list = [trigs] if isinstance(trigs, str) else trigs
                self.tr_store.append([out, ", ".join(t_list)])

            self._validate_current_ui()
            return

        self.editor_stack.set_visible_child_name("mapping")
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

    def _on_vi_cell_edited(self, _widget, path, new_text: str) -> None:
        self.vi_store[path][2] = new_text.strip()
        self._validate_current_ui()

    def _on_pin_cell_edited(self, _widget, path, new_text: str) -> None:
        self.pin_store[path][2] = new_text.strip()
        self._validate_current_ui()

    def _on_tr_cell_edited(self, _widget, path, new_text: str, col: int) -> None:
        self.tr_store[path][col] = new_text.strip()
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

    def _on_add_tr_rule(self, _btn) -> None:
        self.tr_store.append(["", ""])
        self._validate_current_ui()

    def _on_delete_tr_rule(self, _btn) -> None:
        sel = self.tr_tree.get_selection()
        model, treeiter = sel.get_selected()
        if treeiter is not None:
            model.remove(treeiter)
            self._validate_current_ui()

    def _collect_store_rules(self, store: Gtk.ListStore) -> Dict[str, List[str]]:
        rules_dict: Dict[str, List[str]] = {}
        for row in store:
            out, trigs_str = row[0].strip(), row[1].strip()
            trigs = [t.strip() for t in trigs_str.split(",") if t.strip()]
            if out in rules_dict:
                rules_dict[out].extend(trigs)
            else:
                rules_dict[out] = trigs if trigs else [""]
        return rules_dict

    def _collect_mapping_ui(self) -> Tuple[List[dict], Dict[str, List[str]]]:
        diacritics_list: List[dict] = []
        for row in self.dia_store:
            trigs = [t.strip() for t in row[2].split(",") if t.strip()]
            bases = [b.strip() for b in row[3].split(",") if b.strip()]
            diacritics_list.append({
                "name": row[0],
                "combining": row[1],
                "triggers": trigs,
                "bases": bases,
            })
        return diacritics_list, self._collect_store_rules(self.rule_store)

    def _validate_current_ui(self) -> List[ValidationIssue]:
        cat = self._pack_category(self.current_pack_id)

        if cat == "vietnamese":
            seen_keys: Dict[str, str] = {}
            issues: List[ValidationIssue] = []
            for row in self.vi_store:
                op_code, op_label, keys_str = row[0], row[1], row[2]
                keys = [k.strip().lower() for k in keys_str.split(",") if k.strip()]
                if not keys:
                    issues.append(ValidationIssue("C-VI-03", "ERROR", f"Thiếu phím gõ cho {op_label}"))
                for k in keys:
                    if len(k) != 1 or k.isspace():
                        issues.append(ValidationIssue("C-VI-04", "ERROR", f"Phím '{k}' của {op_label} phải là 1 ký tự duy nhất"))
                    elif k in seen_keys and not (
                        {seen_keys[k], op_code} <= {"MARK_HORN", "MARK_BREVE"}
                    ):
                        issues.append(ValidationIssue("C-VI-01", "ERROR", f"Trùng phím '{k}' giữa {seen_keys[k]} và {op_code}"))
                    else:
                        seen_keys[k] = op_code
            return self._render_validation_status(issues, "Bảng phím Tiếng Việt hợp lệ.")

        if cat == "pinyin":
            seen_keys = {}
            issues = []
            for row in self.pin_store:
                op_code, op_label, keys_str = row[0], row[1], row[2]
                keys = [k.strip().lower() for k in keys_str.split(",") if k.strip()]
                if not keys:
                    issues.append(ValidationIssue("C-PIN-03", "ERROR", f"Thiếu phím gõ cho {op_label}"))
                for k in keys:
                    if len(k) != 1 or k.isspace():
                        issues.append(ValidationIssue("C-PIN-04", "ERROR", f"Phím '{k}' của {op_label} phải là 1 ký tự duy nhất"))
                    elif k in seen_keys:
                        issues.append(ValidationIssue("C-PIN-01", "ERROR", f"Trùng phím '{k}' giữa {seen_keys[k]} và {op_code}"))
                    else:
                        seen_keys[k] = op_code
            return self._render_validation_status(issues, "Bảng phím Pinyin hợp lệ.")

        if cat == "translit":
            rules_dict = self._collect_store_rules(self.tr_store)
            issues = validate_generic_rules(rules_dict)
            if self.current_pack_id == "ru":
                s_key = self.ru_stress_entry.get_text().strip()
                if s_key and any(s_key in trigs for trigs in rules_dict.values()):
                    issues.append(
                        ValidationIssue("C-RU-01", "ERROR", f"Phím dấu trọng âm '{s_key}' đang trùng với một quy tắc chữ cái.")
                    )
            return self._render_validation_status(issues, "Bảng chuyển tự hợp lệ, không có xung đột.")

        diacritics_list, rules_dict = self._collect_mapping_ui()
        combined_rules = expand_diacritics_to_rules(diacritics_list)
        for out, trigs in rules_dict.items():
            combined_rules.setdefault(out, []).extend(trigs)

        issues = validate_generic_rules(combined_rules)
        return self._render_validation_status(issues, "Bộ quy tắc hợp lệ, không có xung đột.")

    def _render_validation_status(
        self, issues: List[ValidationIssue], ok_msg: str
    ) -> List[ValidationIssue]:
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
                f"<b><span foreground='#388e3c'>✓ {ok_msg}</span></b>"
            )
            self.btn_save_pack.set_sensitive(True)
        return issues

    def _on_save_pack(self, _btn) -> None:
        cat = self._pack_category(self.current_pack_id)

        if cat == "vietnamese":
            new_bindings: Dict[str, object] = {}
            for row in self.vi_store:
                op_code, keys_str = row[0], row[2]
                keys = [k.strip() for k in keys_str.split(",") if k.strip()]
                new_bindings[op_code] = keys if len(keys) > 1 else (keys[0] if keys else "")

            new_options = {
                "tone_style": self.vi_tone_combo.get_active_id() or "modern",
                "validate": "strict",
                "restore_invalid": self.vi_restore_chk.get_active(),
            }
            _, pack_issues = self.manager.save_user_override(
                pack_id=self.current_pack_id,
                options=new_options,
                bindings=new_bindings,  # type: ignore
            )
            errors = [i for i in pack_issues if i.level == "ERROR"]
            if errors:
                self.manager.reset_user_override(self.current_pack_id)
                self.status_label.set_markup(
                    f"<b><span foreground='#d32f2f'>Lỗi kiểm thử vòng: {errors[0].message}</span></b>"
                )
                return

            self.status_label.set_markup(
                f"<b><span foreground='#1976d2'>✓ Đã lưu cấu hình {self.current_pack_id} (IBus tự động cập nhật).</span></b>"
            )
            return

        if cat == "pinyin":
            new_bindings = {}
            for row in self.pin_store:
                op_code, keys_str = row[0], row[2]
                keys = [k.strip() for k in keys_str.split(",") if k.strip()]
                new_bindings[op_code] = keys if len(keys) > 1 else (keys[0] if keys else "")

            new_options = {
                "validate": "strict",
                "restore_invalid": self.pin_restore_chk.get_active(),
                "v_as_umlaut": self.pin_v_umlaut_chk.get_active(),
            }
            self.manager.save_user_override(
                pack_id=self.current_pack_id,
                options=new_options,
                bindings=new_bindings,  # type: ignore
            )
            self.status_label.set_markup(
                f"<b><span foreground='#1976d2'>✓ Đã lưu cấu hình {self.current_pack_id} (IBus tự động cập nhật).</span></b>"
            )
            return

        if cat == "translit":
            rules_dict = self._collect_store_rules(self.tr_store)
            base_rules = self.current_base_data.get("rules", {})
            disabled = [out for out in base_rules if out not in rules_dict]

            new_options = dict(self.current_base_data.get("options", {}))
            if self.current_pack_id == "ru":
                s_key = self.ru_stress_entry.get_text().strip() or "'"
                new_options["combining_marks"] = {
                    s_key: {"combining": "\u0301", "bases": "аеиоуыэюя"}
                }
            elif self.current_pack_id == "ja_hiragana":
                new_options["double_consonant_sokuon"] = self.ja_sokuon_chk.get_active()

            self.manager.save_user_override(
                pack_id=self.current_pack_id,
                options=new_options,
                rules=rules_dict,
                disable=disabled,
                upper=self.current_base_data.get("upper", {}),
            )
            self.status_label.set_markup(
                f"<b><span foreground='#1976d2'>✓ Đã lưu ghi đè cho {self.current_pack_id} (IBus tự động cập nhật).</span></b>"
            )
            return

        diacritics_list, rules_dict = self._collect_mapping_ui()
        base_rules = self.current_base_data.get("rules", {})
        disabled = [out for out in base_rules if out not in rules_dict]

        self.manager.save_user_override(
            pack_id=self.current_pack_id,
            diacritics=diacritics_list,
            rules=rules_dict,
            disable=disabled,
            upper=self.current_base_data.get("upper", {}),
        )
        self.status_label.set_markup(
            f"<b><span foreground='#1976d2'>✓ Đã lưu ghi đè cho {self.current_pack_id} (IBus tự động cập nhật).</span></b>"
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
                    f"<b><span foreground='#d32f2f'>Lỗi: Trùng phím tắt '{hk}' giữa {seen_hk[hk_norm]} và {pid}!</span></b>"
                )
                return
            seen_hk[hk_norm] = pid
            hotkeys[hk] = pid

        self.manager.save_settings({
            "enabled_packs": enabled,
            "hotkeys": hotkeys,
            "notifications": self.chk_notify.get_active(),
        })
        self.gen_status_label.set_markup(
            "<b><span foreground='#388e3c'>✓ Đã lưu cài đặt chung và phím tắt!</span></b>"
        )


if __name__ == "__main__":
    win = SettingsWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()