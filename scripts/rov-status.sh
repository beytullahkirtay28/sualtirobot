#!/bin/bash
# ROV sistem durumu özeti

echo "============================================================"
echo "  RÜSUMAT 4 - SİSTEM DURUMU"
echo "============================================================"
echo ""

echo "▶ rov-beyin servisi:"
sudo systemctl is-active rov-beyin && \
    echo "  ✅ AKTİF" || echo "  ❌ ÇALIŞMIYOR"
sudo systemctl is-enabled rov-beyin 2>/dev/null && \
    echo "  ✅ Boot'ta otomatik başlıyor" || echo "  ⚠ Otomatik başlatma kapalı"

echo ""
echo "▶ rov-kamera servisi:"
sudo systemctl is-active rov-kamera && \
    echo "  ✅ AKTİF" || echo "  ❌ ÇALIŞMIYOR"
sudo systemctl is-enabled rov-kamera 2>/dev/null && \
    echo "  ✅ Boot'ta otomatik başlıyor" || echo "  ⚠ Otomatik başlatma kapalı"

echo ""
echo "▶ Arduino USB:"
ARDUINO=$(ls /dev/serial/by-id/ 2>/dev/null | head -1)
if [ -n "$ARDUINO" ]; then
    echo "  ✅ /dev/serial/by-id/$ARDUINO"
else
    echo "  ❌ Arduino USB cihazı bulunamadı"
fi

echo ""
echo "▶ Kamera donanım:"
libcamera-hello --list-cameras 2>/dev/null | grep -E "^[0-9]" | sed 's/^/  /'

echo ""
echo "▶ Ağ:"
ip -4 addr show | grep -oP 'inet \K[\d.]+/\d+' | sed 's/^/  /'

echo ""
echo "▶ Son 5 satır rov-beyin log:"
sudo journalctl -u rov-beyin -n 5 --no-pager 2>/dev/null | tail -5 | sed 's/^/  /'

echo ""
echo "▶ Son 5 satır rov-kamera log:"
sudo journalctl -u rov-kamera -n 5 --no-pager 2>/dev/null | tail -5 | sed 's/^/  /'

echo ""
echo "============================================================"
