#!/bin/bash
# ROV servislerini Pi'a kurar (tek seferlik kurulum komutu)
# Önceki rusumat_beyin / rusumat_kamera servislerini de temizler

set -e

ROV_DIR="$HOME/Desktop/ROV"

echo "============================================================"
echo "  RÜSUMAT 4 - SERVİS KURULUMU"
echo "============================================================"
echo ""

if [ ! -f "$ROV_DIR/rov-beyin.service" ] || [ ! -f "$ROV_DIR/rov-kamera.service" ]; then
    echo "❌ Servis dosyaları bulunamadı: $ROV_DIR/"
    echo "   Önce 'cd $ROV_DIR && git pull' yap."
    exit 1
fi

echo "▶ Eski servisleri temizliyor (rusumat_beyin, rusumat_kamera)..."
sudo systemctl stop rusumat_beyin rusumat_kamera 2>/dev/null || true
sudo systemctl disable rusumat_beyin rusumat_kamera 2>/dev/null || true
sudo rm -f /etc/systemd/system/rusumat_beyin.service
sudo rm -f /etc/systemd/system/rusumat_kamera.service
sudo systemctl reset-failed 2>/dev/null || true

echo "▶ Helper script'lere yürütme izni..."
chmod +x "$ROV_DIR/scripts/"*.sh

echo "▶ Yeni servisleri kuruyor..."
sudo cp "$ROV_DIR/rov-beyin.service"  /etc/systemd/system/
sudo cp "$ROV_DIR/rov-kamera.service" /etc/systemd/system/

echo "▶ systemd reload..."
sudo systemctl daemon-reload

echo "▶ Boot'ta otomatik başlat..."
sudo systemctl enable rov-beyin rov-kamera

echo "▶ Şimdi başlat..."
sudo systemctl start rov-beyin
sudo systemctl start rov-kamera

sleep 5

echo ""
echo "▶ Durum:"
sudo systemctl is-active rov-beyin && echo "  rov-beyin:  ✅" || echo "  rov-beyin:  ❌"
sudo systemctl is-active rov-kamera && echo "  rov-kamera: ✅" || echo "  rov-kamera: ❌"

echo ""
echo "============================================================"
echo "  KURULUM TAMAM"
echo "============================================================"
echo ""
echo "Kullanışlı komutlar:"
echo "  bash $ROV_DIR/scripts/rov-status.sh    # durum özeti"
echo "  bash $ROV_DIR/scripts/rov-logs.sh      # canlı log"
echo "  bash $ROV_DIR/scripts/rov-restart.sh   # restart"
echo ""
