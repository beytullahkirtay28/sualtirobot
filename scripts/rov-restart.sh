#!/bin/bash
# ROV servislerini yeniden başlat

echo "🔄 ROV servisleri yeniden başlatılıyor..."

sudo systemctl reset-failed rov-beyin rov-kamera 2>/dev/null

sudo systemctl restart rov-beyin
sudo systemctl restart rov-kamera

sleep 3

echo ""
echo "▶ Durum:"
sudo systemctl is-active rov-beyin && echo "  rov-beyin:  ✅" || echo "  rov-beyin:  ❌"
sudo systemctl is-active rov-kamera && echo "  rov-kamera: ✅" || echo "  rov-kamera: ❌"
echo ""
echo "Canlı log için: sudo journalctl -u rov-beyin -u rov-kamera -f"
