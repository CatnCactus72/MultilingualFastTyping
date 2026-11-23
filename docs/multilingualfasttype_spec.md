# MultilingualFastType: Đặc tả tổng quát
*Phiên bản 0.6, 22/11/2026. Cập nhật từ bản 0.5: chuẩn hóa kiến trúc Plugin 1 thư mục = 1 ngôn ngữ, lớp nền `BaseMarkComposer`, định hướng Tiếng Trung (`zh`) và kiến trúc Giai đoạn 3 (`ru`, `ja`).*

---

## 1. Tổng quan

### 1.1 Mục tiêu
Cho phép gõ nhiều ngôn ngữ chỉ bằng bàn phím Latin thông thường, không đổi layout vật lý và không phải sao chép từ công cụ dịch. Nền tảng đầu tiên là Linux qua **IBus** (Python 3, PyGObject, GTK 3). Hệ điều hành khác và các khác biệt chuyên sâu giữa X11/Wayland được nghiên cứu ở các giai đoạn sau.

### 1.2 Nguyên tắc thiết kế

| Mã | Nguyên tắc |
| :--- | :--- |
| **N-01** | Người dùng tự do gán phím. Ứng dụng chặn mọi cấu hình mâu thuẫn trước khi lưu. |
| **N-02** | Chỉ thay phần ký tự cần thay. Phím thường đi qua nguyên vẹn (`Passthrough`), không phá game hay phím tắt. |
| **N-03** | Mỗi gói ngôn ngữ nằm gọn trong một thư mục độc lập dưới `languages/`. Xung đột không xuyên gói. |
| **N-04** | Core không biết trước ngôn ngữ cụ thể. Mỗi ngôn ngữ là một plugin đăng ký composer qua `core/registry.py`. |
| **N-05** | Bộ gõ làm việc theo thứ tự logic (thứ tự gõ). Đảo chiều hiển thị (Bidi) và tạo hình chữ do ứng dụng/OS lo. |
| **N-06** | Mỗi giai đoạn chỉ thêm một năng lực khó mới. Lớp nền dùng chung được xây trước giai đoạn cần nó đầu tiên. |
| **N-07** | Dữ liệu ngôn ngữ cố định tách khỏi cấu hình ghi đè của người dùng. |
| **N-08** | Phát triển nhanh, làm đơn giản trước, hoàn thiện sau. |

### 1.3 Ngoài phạm vi hiện tại
Hệ điều hành ngoài Linux, nhận dạng giọng nói và chữ viết tay.

---

## 2. Lộ trình chín giai đoạn

Chia theo cơ chế xử lý và năng lực mới phải xây, không chỉ theo hệ chữ. Bốn cơ chế cốt lõi:
* **Cơ chế A:** Ánh xạ chuỗi phím sang ký tự (khớp hậu tố / khớp chuỗi dài nhất).
* **Cơ chế B:** Ghép dấu phụ và thanh điệu lên chữ gốc theo mô hình ô (`BaseMarkComposer`).
* **Cơ chế C:** Ghép âm tiết hoặc cụm chữ phức hợp (bắt buộc dùng Preedit).
* **Cơ chế D:** Chuyển đổi qua danh sách ứng viên (`Candidates`) và từ điển tần suất.

| GĐ | Nội dung | Cơ chế | Năng lực mới | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Latin ánh xạ: Pháp (`FRA`), Đức (`DEU`), Tây Ban Nha (`ESP`), Ý (`ITA`), và mở rộng Ba Lan, Séc, Hung, Na Uy, Romania... | **A** | Nền tảng: `pack.json`, nhóm dấu `diacritics`, phím tắt, System Tray | **Xong** |
| **2** | Latin ghép dấu/thanh: Tiếng Việt (`VNI`, `TLX`); tái sử dụng khung `BaseMarkComposer` cho Pinyin dấu thanh (`PIN`), Yoruba, Navajo | **B** | `BaseMarkComposer` (`MarkCell`, `SyllableBuffer`), chuẩn hóa NFC, kiểm tra âm tiết, tự tách âm tiết viết liền, `Committer` đa chế độ | **Xong (Việt & Pinyin dấu thanh)** |
| **3** | Chữ viết trái-sang-phải không Latin: Tiếng Nga (`RUS`), Tiếng Nhật Hiragana (`JPN`, mở rộng Katakana/Kanji sau), Ukraine, Bulgaria, Hy Lạp, Armenian, Georgian | **A mở rộng** | Bộ khớp chuỗi & tiền tố ưu tiên dài nhất (Longest-Match), xử lý biến âm/gấp đôi phụ âm, `Locale layer` | **Sắp triển khai** |
| **4** | Phải-sang-trái không tạo hình: Hebrew | **A + B** | `Bidi layer`, chọn dạng chữ cuối từ | Chưa |
| **5** | Phải-sang-trái có tạo hình: Ả Rập, Ba Tư, Urdu, Pashto, Kurd, Uyghur; Syriac, Thaana, N'Ko | **A + B** | Dấu harakat, `ZWNJ`/`ZWJ`, Backspace theo cụm | Chưa |
| **6** | Ghép âm tiết bộ nhỏ: Tiếng Hàn (Hangul), Katakana nâng cao, Chú âm | **C** | Preedit bắt buộc, ghép lại có quay lui | Chưa |
| **7** | Chữ ghép cụm: 7a Thái/Lào, 7b chữ Ấn Độ, 7c Khmer/Miến/Tây Tạng/Ethiopic | **C** | Chỉnh sửa theo cụm ký tự, virama và chữ ghép | Chưa |
| **8** | Chuyển đổi qua ứng viên: Tiếng Trung Hán tự (`ZHO`: Pinyin, Chú âm, Cangjie; Giản/Phồn là bộ lọc đầu ra), Tiếng Nhật Kanji, Hanja, Quảng Đông | **D** | `Candidate service`, từ điển tần suất, từ điển cá nhân | Chưa |
| **9** | Ký hiệu và hệ chữ hiếm, cổ, chế tác: IPA, Rune, chữ tượng hình, Tengwar, Braille, Mông Cổ | **A** | Hiển thị dọc, ký tự chọn biến thể | Chưa |

*(Ghi chú: Thêm ngôn ngữ Latin ánh xạ thuần vào GĐ1 chỉ là thêm dữ liệu gói; riêng tiếng Thổ Nhĩ Kỳ bổ sung quy tắc hoa/thường `I`/`ı`, `İ`/`i` qua `Locale layer` ở GĐ3).*

### 2.1 Tiêu chí hoàn thành mỗi giai đoạn
1. Composer và pack có kiểm thử đơn vị (`unittest`) đầy đủ.
2. Bộ kiểm tra xung đột chạy sạch (không lỗi `ERROR`) cho mọi pack của giai đoạn.
3. Composer có trạng thái phải vượt qua kiểm thử vòng (roundtrip).
4. Đã kiểm thử thực tế trên ma trận ứng dụng: GTK, Qt, Chromium, Firefox, Terminal.
5. Có tài liệu hướng dẫn tại `docs/languages/{mã}.md`.
6. Giao diện cài đặt (`SettingsWindow`) hiển thị được lỗi/cảnh báo xung đột tức thời.

### 2.2 Lớp nền xuyên suốt

| Lớp nền | Xây trước giai đoạn | Vị trí mã nguồn |
| :--- | :--- | :--- |
| `Committer` đa chế độ (backspace, micro-preedit theo ứng dụng) | 2 | `core/committer/` |
| Khung ghép dấu chung (`BaseMarkComposer`, `MarkCell`, `SyllableBuffer`) | 2 | `core/composers/marks.py` |
| `Locale layer` (chữ số, dấu câu, hoa/thường đặc thù theo ngôn ngữ) | 3 | `core/layers/locale.py` |
| `Bidi layer` | 4 | `core/layers/bidi.py` |
| Chỉnh sửa theo cụm ký tự (`Cluster`) | 5 (một phần), 7 | `core/layers/cluster.py` |
| `Candidate service` và từ điển | 8 | `core/composers/candidate.py` |

---

## 3. Kiến trúc hệ thống

### 3.1 Luồng xử lý sự kiện phím
```text
Bàn phím vật lý
       │
       ▼
IBus Frontend (ibus_frontend/main.py)
       │  (Kiểm tra Pause, phím tắt Ctrl+Shift+F1..F12, phím modifier)
       ▼
FastTypeEngine (core/engine.py) ──► Registry (core/registry.py)
       │                                    │
       ▼                                    ▼
Composer (Cơ chế A / B / C / D) ◄─── Layers (Unicode, Locale, Bidi, Cluster)
       │
       ▼
Action: Passthrough | Replace(delete_n, text) | Preedit(text) | Candidates(items)
       │
       ▼
Committer (Backspace / Micro-Preedit theo app_profiles.json) ──► Ứng dụng OS
       │
       ⇄ Đồng bộ trạng thái qua state.json (active_pack, paused) ⇄ System Tray / Settings GUI
```
* **Bất biến I1:** Chuỗi đang hiển thị tại con trỏ luôn khớp với `composer.render()`. Giá trị `delete_n` luôn tính theo số **code point** Unicode chuẩn NFC.

### 3.2 Mô hình Plugin: 1 ngôn ngữ = 1 thư mục độc lập
Để hỗ trợ kiến trúc 2 thành phần (**Ứng dụng lõi** + **Gói ngôn ngữ cài thêm**):
* Mỗi ngôn ngữ được đóng gói gọn trong 1 thư mục duy nhất dưới `languages/{mã}/` (hỗ trợ cả thư mục hệ thống `/opt/multilingual-fasttype/languages/` và thư mục cài thêm của người dùng `~/.local/share/multilingual-fasttype/languages/`).
* `PackManager` (`core/pack_manager.py`) và `loader.py` tự động quét các thư mục ngôn ngữ, đọc `manifest.json` (hỗ trợ danh sách `modes` nếu ngôn ngữ có nhiều chế độ gõ như `vi_vni`/`vi_telex` hoặc `zh_pinyin`/`zh_hanzi`), và nạp động file `entry` (mặc định `__init__.py`) qua `importlib` để đăng ký composer vào `core/registry.py`.
* Core không chứa danh sách hardcode các gói ngôn ngữ.

### 3.3 Trạng thái, chỉ báo và khởi động
* **Trạng thái toàn cục (`state.json`):** Lưu `active_pack` (`null` hoặc mã chế độ) và `paused` (`bool`), đồng bộ tức thời qua `mtime` giữa `ibus_frontend`, `tray_icon` và `settings_window`.
* **Chỉ báo trạng thái kép:** System Tray (`AyatanaAppIndicator3`, dự phòng `Gtk.StatusIcon`) và menu `IBus.PropList` trên thanh trạng thái GNOME. Nhãn badge thống nhất dùng **3 chữ cái** (ví dụ `ENG`, `FRA`, `DEU`, `ESP`, `ITA`, `VNI`, `TLX`, `PIN`, `ZHO`, `RUS`, `JPN`, hoặc `||` khi tạm dừng) trên 1 màu nền thống nhất.
* **Khởi động & Đóng gói:** `launcher.py` kích hoạt `ibus-daemon`, chuyển engine `multilingual-fasttype` và khởi chạy khay hệ thống. `install_app.sh` cài đặt ứng dụng vào `/opt/multilingual-fasttype/`. Tự khởi động dùng XDG Autostart tại `~/.config/autostart/multilingual-fasttype.desktop`.

---

## 4. Đặc tả chi tiết theo từng cơ chế

### 4.1 Chuẩn hóa Unicode
* Mọi chuỗi đầu ra đều chuẩn hóa về **NFC** (`unicodedata.normalize("NFC", text)`) để mỗi ô ký tự tương ứng đúng 1 code point, tránh lỗi xóa thiếu dấu tổ hợp trên trình duyệt và terminal.

### 4.2 Cơ chế A: Ánh xạ chuỗi hậu tố (`core/composers/mapping.py`)
* Lưu bộ đệm ngắn các ký tự vừa gõ; khớp hậu tố dài nhất trong `trigger_map`.
* Gõ lặp lại ký tự cuối của trigger ngay sau khi biến đổi sẽ hoàn tác về chuỗi phím thô và khóa trigger đó cho đến khi gặp phím ngắt từ.
* Viết hoa ký tự đầu ra nếu phím chữ cái đầu tiên trong chuỗi trigger viết hoa.

### 4.3 Cơ chế B: Ghép dấu & Thanh điệu theo ô (`core/composers/marks.py`)
* **`BaseMarkComposer`** quản lý danh sách âm tiết trong một từ (`MarkWordState` $\rightarrow$ `List[SyllableBuffer]` $\rightarrow$ `List[MarkCell]`), xử lý hoàn tác, `raw_mode`, `backspace()` lùi ô và tự động khôi phục từ sai chính tả về chuỗi phím thô khi gặp ranh giới từ (`_on_boundary`).
* **Tiếng Việt (`languages/vi/`):**
  * Gồm 2 chế độ: `vi_vni` (`VNI`) và `vi_telex` (`TLX`), dùng chung dữ liệu ngữ âm trong `languages/vi/vi_common/`.
  * Hỗ trợ bỏ dấu tự do vị trí trong âm tiết, dời vị trí dấu thanh động (`hòa` + `n` $\rightarrow$ `hoàn`), hai kiểu đặt dấu thanh (`modern`: *hòa, thủy* / `classic`: *hoà, thuỷ*), ngoại lệ vần mở `ươ` $\rightarrow$ `uơ` (*huơ, thuở*), đồng bộ `uow`/`uwo` $\rightarrow$ `ươ`, khóa cặp `ooo` $\rightarrow$ `oo` (*xoong*) và khôi phục từ tiếng Anh (*windows, test*).
* **Tiếng Trung — Mức 1: Pinyin dấu thanh (`languages/zh/`):**
  * Kế thừa trực tiếp `BaseMarkComposer`: hỗ trợ biến đổi 2 tầng `u` $\rightarrow$ `ü` (`MARK_DIAERESIS`) $\rightarrow$ `ǚ` (`TONE_3`), đặt dấu thanh theo quy tắc `a > o > e` / `iu → u` / `ui → i`, và tự động tách sang `SyllableBuffer` mới khi gõ liền nhiều âm tiết (`cōngmíng`, `nǚ'ér`).

### 4.4 Cơ chế A mở rộng (Giai đoạn 3): Chữ viết trái-sang-phải không Latin (`ru`, `ja`)
Áp dụng kiến trúc 2 tầng cho **Tiếng Nga (`languages/ru/`, `RUS`)** và **Tiếng Nhật (`languages/ja/`, `JPN` — khởi đầu với Hiragana)**:
1. **Tầng 1 — Bộ khớp chuỗi & tiền tố (Longest-Match / Prefix Buffer):**
   * Lưu chuỗi phím Latin đang gõ trong cụm hiện tại, ưu tiên khớp tổ hợp dài nhất (ví dụ tiếng Nhật: `sha`, `shu`, `sho`, `tsu`, `chi` khớp trước `s`, `t`, `c`; tiếng Nga: `sh`, `ch`, `zh`, `yu`, `ya` trước âm đơn).
   * Xử lý gấp đôi phụ âm / biến âm / âm mũi chờ (ví dụ `kka` $\rightarrow$ `っか`, `nn` $\rightarrow$ `ん`), hỗ trợ hoàn tác khi lặp phím và đồng bộ hiển thị qua `Replace(delete_n, text)`.
2. **Tầng 2 — Bộ chuyển đổi ngôn ngữ (Language Adapter):**
   * **Tiếng Nga (`ru`):** Ánh xạ Latin $\rightarrow$ Cyrillic (`а..я`), giữ nguyên trạng thái hoa/thường theo phím gốc.
   * **Tiếng Nhật (`ja`):** Ánh xạ Romaji $\rightarrow$ Hiragana (`あ..ん`), cấu trúc sẵn thư mục để mở rộng Katakana và tầng Kanji (`languages/ja/kanji/`) ở Giai đoạn 8.

### 4.5 Cơ chế D: Ứng viên & Từ điển (Giai đoạn 8 — Hán tự & Kanji)
* Dùng `IBus.LookupTable` chuẩn của hệ điều hành, không tự vẽ cửa sổ popup.
* `CandidateService` nạp từ điển lười (lazy-load), tách tiến trình nếu dữ liệu lớn; từ điển cá nhân lưu cục bộ tại `~/.local/share/multilingual-fasttype/user_dict/`.
* Với **Tiếng Trung Hán tự (`zh_hanzi`, `ZHO`)**: Giản thể (`simplified`) và Phồn thể (`traditional`) là bộ lọc ánh xạ đầu ra ở bước xuất, dùng chung lõi ngữ âm Pinyin.

### 4.6 Phải-sang-trái (Bidi) & Locale layer (Giai đoạn 3–5)
* **Locale layer (`core/layers/locale.py`):** Cấu hình theo ngôn ngữ cho chữ số, dấu câu toàn khổ/đặc thù (`« »`, `„ “`, `。`, `、`) và quy tắc hoa/thường riêng (như `I`/`ı`, `İ`/`i` của tiếng Thổ Nhĩ Kỳ).
* **Bidi layer (`core/layers/bidi.py`):** Commit theo thứ tự logic; hỗ trợ chèn thủ công `LRM`, `RLM`, `ZWNJ`, `ZWJ`.

---

## 5. Định dạng gói ngôn ngữ & Hợp nhất cấu hình

### 5.1 Cấu trúc `manifest.json` (Hỗ trợ đơn chế độ & đa chế độ)
Ví dụ `manifest.json` đa chế độ của gói Tiếng Việt (`languages/vi/manifest.json`):
```json
{
  "id": "vi",
  "name": "Tiếng Việt",
  "version": "1.0.0",
  "script": "latn",
  "entry": "__init__.py",
  "direction": "ltr",
  "stage": 2,
  "schema": 2,
  "modes": [
    {
      "id": "vi_vni",
      "name": "Tiếng Việt (VNI)",
      "composer": "vi_vni",
      "badge": { "label": "VNI" },
      "pack": "vi_vni/pack.json"
    },
    {
      "id": "vi_telex",
      "name": "Tiếng Việt (Telex)",
      "composer": "vi_telex",
      "badge": { "label": "TLX" },
      "pack": "vi_telex/pack.json"
    }
  ]
}
```

### 5.2 Thứ tự hợp nhất & Kiểm tra xung đột
1. **Hợp nhất 3 tầng:** Hồ sơ hệ chữ (`scripts/{script}.json`) $\rightarrow$ Gói ngôn ngữ (`languages/{mã}/...`) $\rightarrow$ Ghi đè của người dùng (`~/.config/multilingual-fasttype/overrides/{mode_id}.json`).
2. **Kiểm tra xung đột (`core/conflicts/`):**
   * Chạy 7 quy tắc chung **G-01..G-07** (trùng trigger, trigger rỗng/chứa khoảng trắng, chuỗi thay thế vòng `A → B → A`, phủ ký tự bắt buộc, cảnh báo tiền tố quy tắc chết...).
   * Chạy kiểm tra đặc thù của composer (`validate_pack`: quy tắc **C-VI-01..C-VI-07** và kiểm thử vòng toàn bộ âm tiết đối với tiếng Việt).

---

## 6. Cấu trúc thư mục dự án

```text
multilingual-fasttype/
├── core/
│   ├── __init__.py
│   ├── engine.py                  # Điều phối sự kiện phím tới Composer qua Registry
│   ├── registry.py                # Bảng đăng ký {composer_name -> ComposerClass}
│   ├── loader.py                  # Hợp nhất 3 tầng & nạp động plugin ngôn ngữ (importlib)
│   ├── pack_manager.py            # Quét gói cài sẵn & cài thêm, quản lý settings & state
│   ├── state_sync.py              # Đồng bộ state.json qua mtime
│   ├── committer/                 # Tầng xuất ký tự đa chế độ theo ứng dụng
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── backspace.py
│   │   ├── preedit.py
│   │   └── app_profiles.json
│   ├── composers/
│   │   ├── __init__.py
│   │   ├── base.py                # Giao diện Composer, KeyEvent, ResetEvent, Action
│   │   ├── mapping.py             # Cơ chế A: MappingComposer
│   │   ├── marks.py               # Cơ chế B: BaseMarkComposer, MarkCell, SyllableBuffer
│   │   ├── syllable.py            # Cơ chế C (GĐ6–7)
│   │   └── candidate.py           # Cơ chế D (GĐ8)
│   ├── layers/
│   │   ├── __init__.py
│   │   ├── unicode_utils.py
│   │   ├── locale.py              # GĐ3
│   │   ├── bidi.py                # GĐ4–5
│   │   └── cluster.py             # GĐ5, 7
│   ├── conflicts/
│   │   ├── __init__.py
│   │   ├── framework.py
│   │   └── generic_rules.py       # G-01..G-07
│   └── testing/
│       ├── __init__.py
│       └── roundtrip.py
├── scripts/
│   └── latn.json                  # Hồ sơ hệ chữ Latin dùng chung
├── languages/                     # Mỗi ngôn ngữ nằm gọn trong 1 thư mục độc lập
│   ├── fr/
│   │   ├── manifest.json          # badge: {"label": "FRA"}
│   │   └── pack.json
│   ├── de/
│   │   ├── manifest.json          # badge: {"label": "DEU"}
│   │   └── pack.json
│   ├── es/
│   │   ├── manifest.json          # badge: {"label": "ESP"}
│   │   └── pack.json
│   ├── it/
│   │   ├── manifest.json          # badge: {"label": "ITA"}
│   │   └── pack.json
│   ├── vi/                        # Gói Tiếng Việt (VNI & Telex)
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── vi_common/
│   │   │   ├── __init__.py
│   │   │   ├── syllables.py
│   │   │   ├── state.py
│   │   │   ├── phonotactics.py
│   │   │   ├── bindings.py
│   │   │   └── roundtrip.py
│   │   ├── vi_vni/
│   │   │   ├── __init__.py
│   │   │   ├── pack.json
│   │   │   └── composer.py
│   │   └── vi_telex/
│   │       ├── __init__.py
│   │       ├── pack.json
│   │       └── composer.py
│   ├── zh/                        # Gói Tiếng Trung (Pinyin dấu thanh; mở rộng Hán tự)
│   │   ├── __init__.py
│   │   ├── manifest.json          # badge: {"label": "ZHO"} / chế độ PIN
│   │   ├── phonetics.py
│   │   ├── pinyin_composer.py
│   │   ├── modes/
│   │   │   └── pinyin.json
│   │   └── hanzi/                 # Mở rộng GĐ8: Giản thể & Phồn thể + ứng viên
│   ├── ru/                        # GĐ3: Tiếng Nga (Cyrillic)
│   │   ├── __init__.py
│   │   ├── manifest.json          # badge: {"label": "RUS"}
│   │   ├── pack.json
│   │   └── composer.py
│   └── ja/                        # GĐ3: Tiếng Nhật (Hiragana; mở rộng Katakana/Kanji)
│       ├── __init__.py
│       ├── manifest.json          # badge: {"label": "JPN"}
│       ├── pack.json
│       ├── romaji_table.py
│       ├── composer.py
│       └── kanji/                 # Mở rộng GĐ8
├── gui/
│   ├── settings_window.py
│   └── tray_icon.py
├── ibus_frontend/
│   ├── fasttype.xml
│   └── main.py
├── tests/
│   ├── test_core.py
│   ├── test_registry.py
│   ├── test_loader_merge.py
│   ├── test_m1_packs.py
│   └── test_vi_composer.py
├── install_app.sh
├── launcher.py
└── MultilingualFastType_spec.md
```

**Thư mục dữ liệu lúc chạy (ngoài kho mã nguồn):**
* `~/.config/multilingual-fasttype/`: `settings.json`, `state.json`, `overrides/{mode_id}.json`.
* `~/.local/share/multilingual-fasttype/languages/`: Thư mục chứa các gói ngôn ngữ do người dùng tải hoặc cài thêm.
* `~/.local/share/multilingual-fasttype/user_dict/`: Từ điển cá nhân cục bộ (GĐ8).
* `/opt/multilingual-fasttype/`: Thư mục cài đặt ứng dụng hệ thống.

---

## 7. Danh sách Yêu cầu chức năng (FR)

| Mã | Nội dung yêu cầu | Giai đoạn |
| :--- | :--- | :--- |
| **FR-01..03** | Bắt phím qua IBus, cơ chế xóa & chèn chữ không gây trễ, quản lý bộ đệm ngắn hạn | 1 |
| **FR-05** | Chuyển đổi nhanh giữa các gói ngôn ngữ bằng phím tắt toàn cục (`Ctrl+Shift+F1..F12`) | 1 |
| **FR-06..09** | Đọc cấu hình gói JSON, hỗ trợ ký tự đặc biệt Latin, phân biệt hoa/thường, bật/tắt gói | 1 |
| **FR-10..11** | Giao diện chỉnh sửa quy tắc/nhóm dấu và tùy chỉnh phím tắt | 1 |
| **FR-12..14** | Chỉ báo trạng thái 3 chữ cái trên System Tray & IBus Panel, tự khởi động cùng hệ thống | 1 |
| **FR-15..19** | Hoàn tác khi gõ lặp phím, kiểm tra xung đột quy tắc, file ghi đè người dùng, chế độ Tạm dừng (`Pause`) | 1 |
| **FR-20** | `Registry` và giao diện `Composer` chuẩn hóa | Nền (trước GĐ2) |
| **FR-21** | `Committer` đa chế độ (Backspace & Micro-Preedit) kèm `app_profiles.json` | Nền (trước GĐ2) |
| **FR-22** | `Manifest` đa chế độ, nạp động plugin ngôn ngữ từ thư mục hệ thống & thư mục cài thêm | Nền |
| **FR-23** | Khung kiểm tra xung đột chung `G-01..G-07` và `validate_pack` theo từng composer | Nền |
| **FR-24** | Khung kiểm thử vòng (Roundtrip test harness) | 2 |
| **FR-25** | Khung ghép dấu chung `BaseMarkComposer` (`MarkCell`, `SyllableBuffer`, chuẩn hóa NFC) | 2 |
| **FR-26..28** | Tiếng Việt: gán phím tự do cho 10 phép toán, bỏ dấu tự do vị trí, đặt dấu thanh kiểu mới & kiểu cũ | 2 |
| **FR-29..31** | Tiếng Việt: kiểm tra chính tả 3 mức (`strict`, `relaxed`, `off`), hoàn tác & Backspace theo ô, khôi phục từ sai | 2 |
| **FR-32..33** | Kiểm tra xung đột `C-VI-01..C-VI-07`, test vòng khi lưu, preset VNI/Telex và hộp gõ thử | 2 |
| **FR-34** | `Locale layer` (chữ số, dấu câu, quy tắc hoa/thường theo ngôn ngữ) | 3 |
| **FR-35** | Bộ khớp chuỗi & tiền tố ưu tiên dài nhất (Longest-Match) và xử lý biến âm cho hệ chữ không Latin (`ru`, `ja`) | 3 |
| **FR-36** | `Bidi layer` và phím chèn ký tự điều hướng `LRM`, `RLM`, `ZWNJ`, `ZWJ` | 4, 5 |
| **FR-37** | Composer ghép âm tiết phức hợp với Preedit bắt buộc | 6 |
| **FR-38** | Chỉnh sửa và xóa theo cụm ký tự (`Cluster`) | 5, 7 |
| **FR-39..40** | `Candidate service` (IBus LookupTable), bộ lọc Giản/Phồn thể và từ điển cá nhân cục bộ | 8 |

---

## 8. Quy trình thêm một gói ngôn ngữ mới

1. Xác định hệ chữ, cơ chế xử lý (**A**, **B**, **C** hoặc **D**) và nhãn badge **3 chữ cái** (ví dụ `RUS`, `JPN`, `ZHO`).
2. Tạo thư mục `languages/{mã}/` chứa `manifest.json` và cấu hình gói (`pack.json` hoặc `modes/*.json`).
3. Nếu ngôn ngữ dùng composer có sẵn (`mapping`): không cần viết code Python, `PackManager` tự nạp ngay.
4. Nếu ngôn ngữ cần thuật toán/dữ liệu riêng (như `vi`, `zh`, `ru`, `ja`): cài đặt composer kế thừa `BaseMarkComposer` hoặc `Composer`, đăng ký qua `register_composer()` trong `languages/{mã}/__init__.py`.
5. Viết unit test trong `tests/`, kiểm tra xung đột và chạy thử trên ma trận ứng dụng (GTK, Qt, Chromium, Firefox, Terminal).