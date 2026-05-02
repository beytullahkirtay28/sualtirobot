#!/bin/bash
#
# Arduino USB cihazini yazilim ile yeniden enumere et
# (kabloyu cikar+tak ile ayni etkiyi yapar).
#
# Pi5'te CH340 chip'li clone Arduino boot sirasinda bazen duzgun
# enumere olmuyor; bu script /sys uzerinden USB device'i deauthorize +
# reauthorize ederek yeniden enumere olmasini saglar.
#
# Calismasi icin root yetkisi gerekli (systemd ExecStartPre=+... ile).

# Tanidik USB-Serial vendor ID'leri:
#   1a86 = QinHeng (CH340/CH341)
#   2341 = Arduino LLC
#   2a03 = Arduino SRL
#   0403 = FTDI
#   10c4 = Silicon Labs (CP210x)
VENDORS="1a86 2341 2a03 0403 10c4"

found=0
for usb_dir in /sys/bus/usb/devices/*/; do
    vendor_file="${usb_dir}idVendor"
    [ -f "$vendor_file" ] || continue
    vendor=$(cat "$vendor_file" 2>/dev/null)

    for v in $VENDORS; do
        if [ "$vendor" = "$v" ]; then
            port=$(basename "$usb_dir")
            authorized="${usb_dir}authorized"

            if [ -w "$authorized" ]; then
                echo "[USB-RESET] Yeniden enumere ediliyor: $port (vendor=$vendor)"
                echo 0 > "$authorized"
                sleep 0.5
                echo 1 > "$authorized"
                sleep 2     # USB re-enumeration icin bekle
                found=1
            else
                echo "[USB-RESET] $authorized yazilamiyor (yetki sorunu)"
            fi
            break
        fi
    done
done

if [ "$found" = "0" ]; then
    echo "[USB-RESET] Tanidik bir USB-Serial cihaz bulunamadi (Arduino takili degil?)"
fi

exit 0   # asla fail etme, rov-beyin yine de baslatilsin
