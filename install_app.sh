#!/usr/bin/env bash
# install_app.sh — Gỡ bản cũ và đóng gói, cài đặt Multilingual FastType vào hệ thống
set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/multilingual-fasttype"
BIN_PATH="/usr/local/bin/multilingual-fasttype"
IBUS_XML="/usr/share/ibus/component/fasttype.xml"
DESKTOP_FILE="/usr/share/applications/multilingual-fasttype.desktop"
ICON_PATH="/usr/share/pixmaps/multilingual-fasttype.svg"

echo "=== 1. Dọn dẹp bản cài đặt cũ ==="
pkill -f "$INSTALL_DIR" 2>/dev/null || true
pkill -f "gui/tray_icon.py" 2>/dev/null || true
pkill -f "gui/settings_window.py" 2>/dev/null || true

sudo rm -rf "$INSTALL_DIR"
sudo rm -f "$BIN_PATH" "$IBUS_XML" "$DESKTOP_FILE" "$ICON_PATH"

# Xóa cache icon cũ để sinh lại bộ badge 3 chữ cái 1 màu
rm -rf "$HOME/.config/multilingual-fasttype/icons"

echo "=== 2. Cài đặt mã nguồn mới vào $INSTALL_DIR ==="
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r \
    "$SRC_DIR/core" \
    "$SRC_DIR/scripts" \
    "$SRC_DIR/languages" \
    "$SRC_DIR/gui" \
    "$SRC_DIR/ibus_frontend" \
    "$SRC_DIR/launcher.py" \
    "$INSTALL_DIR/"

sudo find "$INSTALL_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

sudo chmod +x "$INSTALL_DIR/launcher.py"
sudo chmod +x "$INSTALL_DIR/ibus_frontend/main.py"
sudo chmod +x "$INSTALL_DIR/gui/tray_icon.py"
sudo chmod +x "$INSTALL_DIR/gui/settings_window.py"

echo "=== 3. Tạo biểu tượng ứng dụng & lệnh thực thi ==="
sudo tee "$ICON_PATH" > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect x="8" y="8" width="112" height="112" rx="24" ry="24" fill="#1565c0"/>
  <text x="64" y="82" font-family="sans-serif" font-size="56" font-weight="bold"
        fill="#ffffff" text-anchor="middle">FT</text>
</svg>
EOF

sudo tee "$BIN_PATH" > /dev/null << EOF
#!/usr/bin/env bash
exec /usr/bin/python3 "$INSTALL_DIR/launcher.py" "\$@"
EOF
sudo chmod +x "$BIN_PATH"

echo "=== 4. Đăng ký Component với IBus ==="
sudo tee "$IBUS_XML" > /dev/null << EOF
<?xml version="1.0" encoding="utf-8"?>
<component>
    <name>org.freedesktop.IBus.MultilingualFastType</name>
    <description>Multilingual FastType Component</description>
    <exec>/usr/bin/python3 $INSTALL_DIR/ibus_frontend/main.py --ibus</exec>
    <version>0.5.0</version>
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
            <description>Bộ gõ nhanh đa ngôn ngữ (FRA, DEU, ESP, ITA, VNI, TLX)</description>
            <rank>99</rank>
        </engine>
    </engines>
</component>
EOF

echo "=== 5. Tạo Desktop Entry trong Menu ứng dụng ==="
sudo tee "$DESKTOP_FILE" > /dev/null << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Multilingual FastType
Comment=Bộ gõ nhanh đa ngôn ngữ (FRA, DEU, ESP, ITA, VNI, TLX)
Exec=$BIN_PATH
Icon=$ICON_PATH
Terminal=false
Categories=Utility;Settings;
Keywords=keyboard;input;ime;fasttype;language;vietnamese;
Actions=Settings;

[Desktop Action Settings]
Name=Mở Cài đặt (Settings)
Exec=$BIN_PATH --settings
EOF

echo "=== 6. Làm mới cache IBus và Desktop ==="
ibus write-cache || true
ibus restart || true
sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true

echo "=== Hoàn tất cài đặt Multilingual FastType! ==="