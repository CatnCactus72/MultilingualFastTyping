#!/usr/bin/env bash
# install_m2.sh
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_PY="$PROJECT_DIR/ibus_frontend/main.py"
XML_OUT="$PROJECT_DIR/ibus_frontend/fasttype.xml"

chmod +x "$MAIN_PY"

cat > "$XML_OUT" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<component>
    <name>org.freedesktop.IBus.MultilingualFastType</name>
    <description>Multilingual FastType Component</description>
    <exec>/usr/bin/python3 $MAIN_PY --ibus</exec>
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
            <icon>input-keyboard</icon>
            <layout>us</layout>
            <longname>Multilingual FastType</longname>
            <description>Gõ nhanh đa ngôn ngữ (FR, DE, ES, IT)</description>
            <rank>99</rank>
        </engine>
    </engines>
</component>
EOF

echo "1. Cài đặt file cấu hình IBus vào /usr/share/ibus/component/fasttype.xml (cần sudo)..."
sudo cp "$XML_OUT" /usr/share/ibus/component/fasttype.xml

echo "2. Xóa cache của IBus và khởi động lại ibus-daemon..."
ibus write-cache || true
ibus restart || true

echo "Hoàn tất! Bạn có thể kích hoạt bộ gõ bằng lệnh:"
echo "  ibus engine multilingual-fasttype"