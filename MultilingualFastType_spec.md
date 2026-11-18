# Đặc tả dự án MultilingualFastType

Phiên bản 0.1 (bản nháp) · 13/11/2026 · Phạm vi: giai đoạn 1–2, chạy thử trên Linux

## 1. Tổng quan

### 1.1 Mục tiêu

Ứng dụng giúp người học và người dùng nhiều ngôn ngữ gõ được ký tự đặc biệt của nhiều ngôn ngữ **chỉ bằng bàn phím Latin thông thường**, không phải đổi bộ gõ của hệ điều hành và không phải copy-paste từ công cụ dịch. Khác với Telex/VNI, **quy tắc gõ do người dùng tự quyết định** (ví dụ gõ `ae` hoặc `a:` đều có thể ra `ä`), và ứng dụng cảnh báo ngay khi các quy tắc xung đột nhau.

### 1.2 Lộ trình ngôn ngữ dài hạn

| Giai đoạn | Nhóm ngôn ngữ | Ghi chú |
| --- | --- | --- |
| 1 | Latin có ký tự đặc biệt: Pháp, Đức, Tây Ban Nha, Ý | **Thuộc phạm vi bản này** |
| 2 | Na Uy, Ba Lan, Việt | Na Uy và Ba Lan thuộc phạm vi bản này. Tiếng Việt cần luật đặt dấu thanh nên tách ra làm riêng (mục 8, mốc M6) |
| 3 | Cyrillic, Ả Rập | Chưa đặc tả |
| 4 | Thái, Khmer | Chưa đặc tả |
| 5 | Trung, Hàn, Nhật | Cần kiến trúc khác (từ điển, cửa sổ chọn ứng viên). Chưa đặc tả |

### 1.3 Trong phạm vi

- Linux, một người dùng, chạy cục bộ.
- Gói ngôn ngữ Pháp, Đức, Tây Ban Nha, Ý; sau đó Na Uy, Ba Lan.
- Chế độ gõ cố định (lock mode) chọn bằng phím tắt.
- Quy tắc ánh xạ *cách gõ → ký tự* do người dùng tự sửa, có kiểm tra xung đột.
- Chỉ báo cho biết ngôn ngữ đang bật.

### 1.4 Ngoài phạm vi (hiện tại)

- Windows, macOS.
- Chế độ gõ nội tuyến (Inline Mode, FR-04 cũ): loại bỏ.
- Chỉ báo nổi gần con trỏ (HUD, FR-12 cũ): hoãn.
- Tiếng Việt, Cyrillic, Ả Rập, Thái, Khmer, Trung, Hàn, Nhật.
- Đồng bộ cấu hình giữa các máy, tài khoản, kết nối mạng.

### 1.5 Nguyên tắc phát triển

Làm theo kiểu agile, “ngây thơ” trước: mỗi mốc (mục 8) phải chạy được và dùng được; chưa xử lý trường hợp biên khi chưa gặp; lỗi nào gặp thật thì sửa ở mốc sau. Ở giai đoạn đầu **chưa xét khác biệt X11/Wayland hay môi trường desktop**.

## 2. Thuật ngữ

| Thuật ngữ | Ý nghĩa |
| --- | --- |
| Gói ngôn ngữ (pack) | Một file JSON chứa tập quy tắc của một ngôn ngữ |
| Quy tắc (rule) | Một cặp *cách gõ → ký tự đầu ra* |
| Trigger (cách gõ) | Chuỗi phím gõ ra để kích hoạt quy tắc, ví dụ `ae` |
| Đầu ra | Ký tự (hoặc chuỗi ký tự) thay thế trigger, ví dụ `ä` |
| Bộ đệm | Danh sách ngắn các phím vừa gõ, dùng để đối chiếu với trigger |
| Passthrough | Để phím đi nguyên bản tới ứng dụng, không can thiệp |
| Hoàn tác (revert) | Gõ lại phím cuối của trigger ngay sau khi biến đổi để trả về chuỗi đã gõ |
| Chế độ cố định (lock mode) | Một gói đang bật cho đến khi người dùng tắt hoặc đổi gói |

## 3. Quyết định và giả định

| ID | Quyết định | Ghi chú |
| --- | --- | --- |
| D-01 | Nền tảng đầu tiên: Linux. Chưa xét X11/Wayland/desktop | Làm “ngây thơ”, sửa khi gặp lỗi |
| D-02 | Kiến trúc hai lớp: **lõi (core)** không phụ thuộc nền tảng + **frontend** của từng nền tảng | Để sau này thêm Windows/macOS mà dùng lại quy tắc |
| D-03 | Frontend đầu tiên: engine IBus (giả định) | Chạy được trên X11 và Wayland, không cần quyền root. Nếu không dùng được thì đổi sang hướng khác mà không đổi lõi |
| D-04 | Chỉ dùng chế độ cố định; bỏ chế độ nội tuyến | Thuật toán đơn giản, gõ nhanh hơn |
| D-05 | Không dùng Caps Lock làm phím chuyển. Mặc định `Ctrl+F1`, `F2`... (đổi được) | Caps Lock được trả về chức năng bình thường |
| D-06 | Mỗi lúc chỉ một gói hoạt động; các gói độc lập | Xung đột quy tắc chỉ xảy ra trong cùng một gói |
| D-07 | Passthrough: không dùng vùng soạn thảo (preedit); phím không thuộc quy tắc giữ nguyên | Tránh lỗi “đổi cả ký tự thường” như ibus-bamboo trong game (cần kiểm chứng, xem mục 9) |
| D-08 | Quy tắc áp dụng **ngay khi trigger khớp đầu tiên**, không chờ phím kế tiếp | Đơn giản và dễ đoán |
| D-09 | Hoàn tác bằng cách gõ lại phím cuối của trigger | Kiểu Unikey: `a`,`e` → `ä`; thêm `e` → `ae` |
| D-10 | Hoa/thường dựa vào **chữ cái do hệ điều hành tạo ra** cho phím chữ cái đầu tiên của trigger (Shift hoặc Caps Lock) | `nh` → `ñ`, `Nh`/`NH` → `Ñ` |
| D-11 | Tiếng Việt không nằm trong MVP | Cần luật viết lại theo ngữ cảnh, không chỉ ánh xạ |
| D-12 | Ngôn ngữ lập trình chưa chốt (xem mục 10) | Gợi ý Python cho bản đầu |

## 4. Yêu cầu chức năng

### 4.1 Bảng tổng hợp

Ưu tiên: Must (bắt buộc), Should (nên có), Could (có thể có), Won't (không làm ở bản này).

| ID | Yêu cầu | Ưu tiên | Mốc | Thay đổi so với bản nháp ban đầu |
| --- | --- | --- | --- | --- |
| FR-01 | Nhận phím gõ của ô nhập đang focus | Must | M2 | Đổi từ hook toàn cục sang engine IBus (D-03) |
| FR-02 | Khi khớp quy tắc: xóa phần trigger đã hiện và chèn ký tự đích | Must | M0, M2 | Chỉ tác động khi quy tắc khớp |
| FR-03 | Bộ đệm ngắn hạn; xóa bộ đệm khi gặp phím ngắt | Must | M0 | Độ dài bằng trigger dài nhất; điều kiện xóa ở mục 4.2 |
| FR-04 | Chế độ gõ nội tuyến | Won't | — | Loại bỏ (D-04) |
| FR-05 | Chế độ cố định bật/tắt bằng phím tắt | Must | M2 | Không dùng Caps Lock làm phím chuyển (D-05) |
| FR-06 | Đọc gói ngôn ngữ dạng JSON | Must | M1 | Định dạng ở mục 4.3 |
| FR-07 | Hỗ trợ đầy đủ ký tự đặc biệt Latin của 4 ngôn ngữ | Must | M1 | Danh sách ký tự ở FR-07 bên dưới |
| FR-08 | Phân biệt hoa/thường | Must | M0 | Theo D-10 |
| FR-09 | 4 gói mặc định; bật/tắt từng gói | Must | M1, M3 | “Bật” nghĩa là gói nằm trong danh sách chuyển nhanh |
| FR-10 | Giao diện bảng sửa/thêm quy tắc | Should | M3 | Kèm cảnh báo xung đột trực tiếp (FR-16) |
| FR-11 | Tùy chỉnh phím tắt | Should | M3 | M2: phím cố định trong file cấu hình |
| FR-12 | Chỉ báo ngôn ngữ đang bật | Must (bản đơn giản) | M2, M4 | HUD nổi hoãn; M2 dùng thông báo, M4 dùng biểu tượng |
| FR-13 | Khay hệ thống: chọn nhanh ngôn ngữ, tạm dừng, mở cài đặt | Should | M4 | Phụ thuộc môi trường desktop |
| FR-14 | Tự khởi động cùng hệ thống | Could | M4 |  |
| FR-15 | Hoàn tác bằng gõ lại phím cuối | Must | M0 | Mới (D-09) |
| FR-16 | Kiểm tra xung đột quy tắc | Must | M0, M3 | Mới (mục 4.4) |
| FR-17 | Passthrough cho phím không thuộc quy tắc | Must | M2 | Mới (D-07) |
| FR-18 | File ghi đè của người dùng tách khỏi gói mặc định | Should | M1 | Mới; để cập nhật gói không mất chỉnh sửa |
| FR-19 | Về bộ gõ mặc định (M2) và tạm dừng ứng dụng (M4) | Must / Should | M2, M4 | Mới |

**Chi tiết FR-07 (ký tự cần hỗ trợ):**

- Pháp: `é è ê ë à â î ï ô ù û ü ÿ ç œ æ` và chữ hoa tương ứng.
- Đức: `ä ö ü ß` và chữ hoa `Ä Ö Ü ẞ`.
- Tây Ban Nha: `á é í ó ú ü ñ ¿ ¡` và chữ hoa.
- Ý: `à è é ì í î ò ó ù ú` và chữ hoa.

### 4.2 Thuật toán xử lý phím (lõi)

**Trạng thái** của mỗi ô nhập: gói đang bật (hoặc không có), bộ đệm (danh sách phím thô), `last_transform` (biến đổi vừa xảy ra, nếu có), tập quy tắc đang bị khóa.

Khi **không có gói nào bật**: mọi phím đều passthrough.

Khi có gói bật, với mỗi phím:

1. **Phím kèm Ctrl/Alt/Super** → xóa bộ đệm và `last_transform`, passthrough.
2. **Phím ngắt** (Space, Enter, Tab, Esc, các phím mũi tên, Home, End, Page Up/Down, Delete, Backspace) → xóa bộ đệm, `last_transform` và tập quy tắc bị khóa; passthrough. Nhấp chuột và đổi cửa sổ/ô nhập cũng xóa bộ đệm.
3. **Ký tự in được:**
   1. *Hoàn tác:* nếu `last_transform` tồn tại và ký tự này trùng (không phân biệt hoa/thường) với phím cuối của trigger vừa dùng → xóa đầu ra vừa chèn, chèn lại đúng chuỗi phím thô đã gõ (giữ nguyên hoa/thường), khóa quy tắc đó cho đến khi bộ đệm bị xóa, nuốt phím này. Bộ đệm được đặt lại bằng chuỗi phím thô.
   2. *Khớp quy tắc:* ngược lại, thêm phím vào bộ đệm, tìm quy tắc (không bị khóa) có trigger khớp **hậu tố** của bộ đệm (không phân biệt hoa/thường; nếu nhiều quy tắc khớp thì chọn trigger dài nhất). Nếu khớp: xóa (độ dài trigger − 1) ký tự đang hiển thị, chèn đầu ra, nuốt phím này, ghi `last_transform`, làm rỗng bộ đệm.
   3. *Không khớp:* passthrough, xóa `last_transform`.

**Hoa/thường (FR-08):** đầu ra viết hoa nếu phím chữ cái đầu tiên của trigger là chữ hoa do hệ điều hành tạo ra (Shift hoặc Caps Lock). Chữ hoa của đầu ra lấy theo ánh xạ hoa của Unicode, trừ khi gói khai báo ngoại lệ (ví dụ `ß` → `ẞ`). Trigger không có chữ cái thì không đổi hoa/thường.

**Nguyên tắc an toàn:** khi không chắc bộ đệm còn khớp với văn bản thật, ưu tiên xóa bộ đệm và passthrough hơn là xóa chữ của người dùng.

### 4.3 Định dạng gói ngôn ngữ

```json
{
  "meta": { "id": "de", "name": "Deutsch", "version": 1, "symbol": "DE" },
  "rules": {
    "ä": ["ae", "a:"],
    "ö": "oe",
    "ü": "ue",
    "ß": "sz"
  },
  "upper": { "ß": "ẞ" }
}
```

Quy ước:

- Khóa là **đầu ra** (một hoặc nhiều ký tự Unicode, dạng chuẩn hóa NFC); giá trị là một trigger hoặc một mảng trigger.
- Trigger chỉ gồm ký tự ASCII in được, không chứa khoảng trắng. Chữ cái trong trigger không phân biệt hoa/thường khi khớp.
- Chỉ khai báo dạng chữ thường; chữ hoa tự suy ra, ngoại lệ khai báo trong `upper`.
- Thứ tự quy tắc không ảnh hưởng kết quả.
- Trường `meta.version` để sau này đổi định dạng mà không phá gói cũ.
- File ghi đè của người dùng có cùng cấu trúc: quy tắc cùng đầu ra sẽ thay thế trigger của gói gốc; trường `disable` (danh sách đầu ra) dùng để tắt quy tắc của gói gốc.

### 4.4 Kiểm tra xung đột (FR-16)

Chạy khi nạp gói và mỗi lần người dùng sửa quy tắc.

| Loại | Ví dụ | Mức | Xử lý |
| --- | --- | --- | --- |
| Trùng trigger (kể cả khác hoa/thường) | `ä`: `ae` và `æ`: `ae` | Lỗi | Không cho lưu; chỉ rõ hai quy tắc |
| Trigger rỗng, chứa khoảng trắng hoặc ký tự không in được |  | Lỗi | Không cho lưu |
| Đầu ra rỗng hoặc trùng đúng trigger |  | Lỗi | Không cho lưu |
| Trigger là tiền tố của trigger khác (quy tắc “chết”) | `a:` và `a:b` | Cảnh báo | Quy tắc dài không bao giờ chạy vì quy tắc ngắn áp dụng ngay (D-08) |
| Trigger kết thúc bằng dấu câu thường đứng sau chữ (`: ; , . ! ? '`) | `e:` | Cảnh báo | Gợi ý ký tự ít gặp (`~ ^` và dấu huyền); vẫn dùng được nhờ hoàn tác |
| Trigger dài 1 ký tự | `~` → `ñ` | Cảnh báo | Mọi lần gõ phím đó đều bị thay |

### 4.5 Tệp và thư mục (đề xuất)

- Gói mặc định: thư mục dữ liệu của ứng dụng, chỉ đọc.
- `~/.config/multilingual-fasttype/user/`: file ghi đè của người dùng (một file mỗi gói).
- `~/.config/multilingual-fasttype/settings.json`: danh sách gói được bật, phím tắt, tùy chọn chỉ báo.

### 4.6 Phím tắt mặc định (đề xuất, đổi được)

| Phím | Tác dụng |
| --- | --- |
| `Ctrl+Shift+F1` | Bật tiếng Pháp |
| `Ctrl+Shift+F2` | Bật tiếng Đức |
| `Ctrl+Shift+F3` | Bật tiếng Tây Ban Nha |
| `Ctrl+Shift+F4` | Bật tiếng Ý |
| Nhấn lại đúng phím đang bật | Về bộ gõ mặc định |

Lưu ý: `Ctrl+F1–F4` có thể trùng với phím tắt của KDE (chuyển desktop ảo) hoặc của trình duyệt (`Ctrl+F4` đóng tab). Đây là lý do FR-11 cần có.

### 4.7 Chỉ báo trạng thái

- Mỗi gói có ký hiệu hai chữ (`FR`, `DE`, `ES`, `IT`) và màu riêng; bộ gõ mặc định có ký hiệu riêng, tương tự chữ V đỏ / E xanh của Unikey.
- M2: thông báo ngắn mỗi khi chuyển (ví dụ qua `notify-send`).
- M4: biểu tượng trên khay hệ thống hiển thị ký hiệu hiện tại.

## 5. Yêu cầu phi chức năng

- **Độ trễ:** người dùng không cảm nhận được. Tiêu chí ban đầu: lõi xử lý mỗi phím dưới 1 ms (đo bằng benchmark ở M0). Ngưỡng đầu-cuối đặt sau khi có số đo thật ở M2.
- **Riêng tư:** chạy hoàn toàn cục bộ, không kết nối mạng, không ghi lại nội dung gõ; nhật ký chỉ chứa sự kiện kỹ thuật, không chứa ký tự gõ.
- **Độ tin cậy:** không chắc thì không làm (mục 4.2).
- **Unicode:** đầu ra chuẩn hóa NFC.
- **Khả mở rộng:** gói ngôn ngữ có trường phiên bản; lõi không phụ thuộc IBus.
- **Kiểm thử:** lõi được phủ bằng test tự động theo mục 7.
- **Tài nguyên:** nhẹ, chạy nền liên tục (chưa đặt chỉ tiêu cụ thể).

## 6. Kiến trúc

```
[Bàn phím] → [Frontend: engine IBus] ⇄ [Lõi (core)]
                   │                    ├─ Bộ nạp + kiểm tra quy tắc
                   │                    ├─ Bộ đệm + bộ khớp
                   │                    └─ Xử lý hoa/thường + hoàn tác
                   ├─ Chỉ báo (thông báo / khay hệ thống)
                   └─ Kho cấu hình (~/.config/multilingual-fasttype/)
[Giao diện cài đặt] → Kho cấu hình (+ bộ kiểm tra quy tắc)
```

Giao diện của lõi:

- **Vào:** `KeyEvent { char, is_upper, has_modifier, is_break_key }` và `ResetEvent`.
- **Ra:** `Passthrough` hoặc `Replace { delete_count, text, consume_key }`.

## 7. Ca kiểm thử chấp nhận

Gói thử: `ä` ← `ae`, `ë` ← `e:`, `ñ` ← `nh`, `ß` ← `sz` (chữ hoa `ẞ`).

| # | Chuỗi phím | Kết quả mong đợi |
| --- | --- | --- |
| 1 | `a`, `e` | `ä` |
| 2 | `a`, `e`, `e` | `ae` (hoàn tác) |
| 3 | `a`, `e`, `e`, `e` | `aee` (quy tắc bị khóa sau hoàn tác) |
| 4 | `A`, `e` | `Ä` |
| 5 | `A`, `E` | `Ä` |
| 6 | `a`, `E` | `ä` (phím chữ cái đầu là chữ thường) |
| 7 | `n`, `h` / `N`, `h` / `N`, `H` | `ñ` / `Ñ` / `Ñ` |
| 8 | Bật Caps Lock, gõ `n`, `h` | `Ñ` |
| 9 | `s`, `z` / `S`, `z` | `ß` / `ẞ` |
| 10 | `a`, Space, `e` | `a e` (Space xóa bộ đệm) |
| 11 | `a`, mũi tên trái, `e` | Không biến đổi |
| 12 | `N`,`a`,`m`,`e`,`:` | `Namë` |
| 13 | Như 12, thêm `:` | `Name:` (hoàn tác) |
| 14 | Như 13, thêm `:` | `Name::` (quy tắc đã khóa) |
| 15 | `Ctrl+C` | Passthrough, xóa bộ đệm |
| 16 | Không có gói nào bật, gõ `a`, `e` | `ae` |
| 17 | Nạp gói có hai trigger trùng | Báo lỗi, không nạp |
| 18 | Nạp gói có `a:` và `a:b` | Cảnh báo quy tắc chết |

## 8. Lộ trình theo mốc

| Mốc | Nội dung | Tiêu chí hoàn thành |
| --- | --- | --- |
| M0 | Lõi + bộ kiểm tra xung đột + chạy thử bằng dòng lệnh (mô phỏng chuỗi phím) | Đạt toàn bộ ca kiểm thử mục 7; có benchmark |
| M1 | Bộ nạp JSON + 4 gói Pháp, Đức, Tây Ban Nha, Ý + file ghi đè | Nạp được gói, gói đủ ký tự FR-07 |
| M2 | Engine IBus dạng passthrough + `Ctrl+F1..F4` + về bộ gõ mặc định + thông báo đơn giản | Dùng được hằng ngày trong các ô nhập văn bản thông thường |
| M3 | Giao diện cài đặt: bật/tắt gói, bảng sửa quy tắc, phím tắt | Sửa quy tắc và thấy cảnh báo xung đột ngay trong giao diện |
| M4 | Biểu tượng khay hệ thống, tự khởi động, tạm dừng |  |
| M5 | Gói Na Uy, Ba Lan |  |
| M6 | Nghiên cứu tiếng Việt (đặc tả riêng, cần luật viết lại theo ngữ cảnh) | Có tài liệu thiết kế |

Sau M6: các giai đoạn 3–5 (mỗi giai đoạn một đặc tả riêng).

## 9. Rủi ro đã biết

Chưa xử lý ở bản đầu; sửa khi gặp thật.

| Rủi ro | Mô tả | Hướng xử lý dự kiến |
| --- | --- | --- |
| Lỗi phím trong game | Game đọc phím trực tiếp có thể lỗi khi IBus nằm trong đường đi của phím (chưa kiểm chứng nguyên nhân) | Thử với engine không biến đổi để xác định nguyên nhân; chạy game với `XMODIFIERS=@im=none`; dùng Pause; hoặc chuyển sang hướng evdev/uinput |
| Ứng dụng thiếu hỗ trợ xóa văn bản xung quanh con trỏ | Terminal, một số ứng dụng Electron | Dự phòng bằng phát phím Backspace |
| Phím tắt bị chiếm | `Ctrl+F1–F4` bị desktop hoặc trình duyệt dùng | Cho đổi phím (FR-11) |
| Khay hệ thống | GNOME mặc định không có khay | M2 dùng thông báo; M4 cần extension AppIndicator |
| Cửa sổ nổi | Wayland hạn chế đặt cửa sổ tùy ý | HUD hoãn (FR-12) |
| Trigger trùng văn bản thường | Ví dụ `e:` trong “Name:”, `ss` trong tiếng Đức | Hoàn tác + cảnh báo; chọn trigger mặc định ít va chạm |
| Bộ đệm lệch văn bản thật | Click chuột, kéo thả, đổi focus | Xóa bộ đệm khi nghi ngờ |
| Trạng thái theo từng ô nhập | Engine IBus có thể giữ trạng thái riêng cho từng cửa sổ | Quyết định ở mục 10 |

## 10. Câu hỏi mở

- Ngôn ngữ lập trình: dùng Python 3 (thư viện chuẩn cho Core, PyGObject gi cho IBus và GTK 3 cho GUI/Tray) thay vì để mở.   

- Trạng thái ngôn ngữ: Chốt cơ chế Toàn cục (Global) — trạng thái gói ngôn ngữ đang bật và trạng thái tạm dừng được dùng chung xuyên suốt các cửa sổ ứng dụng (đồng bộ qua state.json), không tách riêng theo từng cửa sổ.

- Quy ước Trigger mặc định: Chốt bộ phím dấu thống nhất theo kiểu VNI (1 = acute, 2 = grave, 3 = diaeresis, 4 = tilde, 5 = cedilla, 6 = circumflex) kết hợp quy tắc chữ ghép ít va chạm (oe, ae, sz, ??, !!), thay cho các ví dụ ký hiệu dấu câu (:, /, ~) ở bản nháp