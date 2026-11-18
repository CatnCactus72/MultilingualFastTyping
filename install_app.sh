#!/usr/bin/env bash
# install_app.sh — Đóng gói và cài đặt Multilingual FastType thành ứng dụng hệ thống
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/multilingual-fasttype"
BIN_PATH="/usr/local/bin/multilingual-fasttype"
IBUS_XML="/usr/share/ibus/component/fasttype.xml"
DESKTOP_FILE="/usr/share/applications/multilingual-fasttype.desktop"
ICON_PATH="/usr/share/pixmaps/multilingual-fasttype.svg"

echo "=== Đang cài đặt Multilingual FastType vào hệ thống ==="

# 1. Sao chép mã nguồn vào /opt/multilingual-fasttype
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$SRC_DIR/core" "$SRC_DIR/packs" "$SRC_DIR/ibus_frontend" "$SRC_DIR/gui" "$SRC_DIR/launcher.py" "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/launcher.py"
sudo chmod +x "$INSTALL_DIR/ibus_frontend/main.py"
sudo chmod +x "$INSTALL_DIR/gui/tray_icon.py"
sudo chmod +x "$INSTALL_DIR/gui/settings_window.py"

# 2. Tạo icon SVG đại diện cho ứng dụng trong App Menu
sudo tee "$ICON_PATH" > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect x="8" y="8" width="112" height="112" rx="24" ry="24" fill="#1565c0"/>
  <text x="64" y="82" font-family="sans-serif" font-size="56" font-weight="bold"
        fill="#ffffff" text-anchor="middle">FT</text>
</svg>
EOF

# 3. Tạo lệnh gọi nhanh /usr/local/bin/multilingual-fasttype
sudo tee "$BIN_PATH" > /dev/null << EOF
#!/usr/bin/env bash
exec /usr/bin/python3 "$INSTALL_DIR/launcher.py" "\$@"
EOF
sudo chmod +x "$BIN_PATH"

# 4. Đăng ký Component với IBus
sudo tee "$IBUS_XML" > /dev/null << EOF
<?xml version="1.0" encoding="utf-8"?>
<component>
    <name>org.freedesktop.IBus.MultilingualFastType</name>
    <description>Multilingual FastType Component</description>
    <exec>/usr/bin/python3 $INSTALL_DIR/ibus_frontend/main.py --ibus</exec>
    <version>0.1.0</version>
    <author>MultilingualFastType Dev</author>
    <license>MIT</license>
    <homepage>https://localhost</homepage>
    <textdomain>multilingual-fasttype</textdomain>
    <engines>
        <engine>
            <name>multilingual-fasttype</name>
            <language>other</language>
            <license>MIT</license>
            <author>MultilingualFastType Dev</author>
            <icon>$ICON_PATH</icon>
            <layout>us</layout>
            <longname>Multilingual FastType</longname>
            <description>Gõ nhanh đa ngôn ngữ (FR, DE, ES, IT)</description>
            <rank>99</rank>
        </engine>
    </engines>
</component>
EOF

# 5. Tạo Desktop Entry để hiển thị trong Menu Ứng dụng (Show Applications)
sudo tee "$DESKTOP_FILE" > /dev/null << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Multilingual FastType
Comment=Bộ gõ nhanh đa ngôn ngữ (FR, DE, ES, IT)
Exec=$BIN_PATH
Icon=$ICON_PATH
Terminal=false
Categories=Utility;Settings;
Keywords=keyboard;input;ime;fasttype;language;
Actions=Settings;

[Desktop Action Settings]
Name=Mở Cài đặt (Settings)
Exec=$BIN_PATH --settings
EOF

# 6. Cập nhật lại đường dẫn Autostart trong gui/tray_icon.py (nếu người dùng bật Tự khởi động)
# Làm mới cache IBus và Desktop
ibus write-cache || true
ibus restart || true
sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true

echo "=== Cài đặt hoàn tất! ==="
echo "- Bạn có thể tìm 'Multilingual FastType' trong Menu Ứng dụng (ấn phím Super/Windows) và bấm vào để chạy."
echo "- Nhấp chuột phải vào biểu tượng ứng dụng và chọn 'Mở Cài đặt (Settings)' để chỉnh sửa quy tắc."