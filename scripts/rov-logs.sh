#!/bin/bash
# ROV iki servisin canlı log'unu birleştirilmiş şekilde gösterir
# Çıkmak için: Ctrl+C

echo "📋 ROV canlı log (Ctrl+C ile çık)"
echo "============================================================"

sudo journalctl -u rov-beyin -u rov-kamera -f --no-pager
