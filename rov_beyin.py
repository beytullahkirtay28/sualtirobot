"""
RÜSUMAT 4 - Beyin (UDP -> Arduino Serial bridge)
Yuzey istasyondan gelen UDP komutlarini Arduino'ya seri port uzerinden iletir.

Ozellikler:
- config.json'dan ayar okur
- /dev/serial/by-id/ symlink desteği (USB sirasi degisirse de bulur)
- DTR/RTS off (port acmak Arduino'yu resetlemez)
- RDY heartbeat bekler (Arduino canli mi kontrol)
- Auto-reconnect (Arduino kopunca yeniden baglanir)
- systemd boot bekleyicisi
"""

import socket
import serial
import time
import json
import os
import glob

# === CONFIG YÜKLE ===
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
try:
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"⚠️  config.json okunamadı: {e} — varsayılanlar kullanılıyor")
    CONFIG = {
        "network": {"udp_port": 5005},
        "arduino": {
            "baud_rate": 115200,
            "ports": ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1", "/dev/ttyACM1"]
        }
    }

UDP_IP   = "0.0.0.0"
UDP_PORT = CONFIG['network']['udp_port']

ARDUINO_PORTS_DEFAULT = CONFIG['arduino']['ports']
BAUD_RATE             = CONFIG['arduino']['baud_rate']

# Zaman ayarlari
ARDUINO_RETRY_SN  = 3.0
SOCKET_TIMEOUT_SN = 1.0

print("=" * 50)
print("RÜSUMAT 4 - BEYİN (UDP -> SERIAL) BAŞLATILIYOR")
print("=" * 50)


def find_arduino_ports():
    """Arduino'yu bul. Once stable by-id symlink, sonra default port listesi."""
    # 1) Stable: /dev/serial/by-id/usb-Arduino*
    by_id = sorted(glob.glob('/dev/serial/by-id/*Arduino*') +
                   glob.glob('/dev/serial/by-id/*arduino*') +
                   glob.glob('/dev/serial/by-id/*CH340*') +
                   glob.glob('/dev/serial/by-id/*FTDI*'))
    if by_id:
        return by_id

    # 2) Fallback: /dev/ttyUSB*, /dev/ttyACM*
    return [p for p in ARDUINO_PORTS_DEFAULT if os.path.exists(p)]


def arduino_bagla():
    """Arduino'ya baglan, RDY heartbeat'i bekle. Basarisizsa None."""
    ports = find_arduino_ports()
    if not ports:
        return None

    for port in ports:
        try:
            # DTR/RTS off ile aç → Arduino reset olmaz, mevcut sketch devam eder
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = BAUD_RATE
            ser.timeout = 1
            ser.dtr = False
            ser.rts = False
            ser.open()

            print(f"⏳ {port} açıldı (DTR/RTS off), Arduino RDY bekleniyor...")
            deadline = time.time() + 4.0
            while time.time() < deadline:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line == "RDY":
                    print(f"✅ Arduino hazır: {port}")
                    ser.reset_input_buffer()
                    return ser

            print(f"⚠️  {port}: RDY gelmedi ama port açık, kullanılıyor")
            return ser

        except Exception as e:
            print(f"⚠️  {port} açılamadı: {e}")
    return None


def main():
    # systemd boot algilanirsa USB hazirligi icin bekle
    if os.environ.get('INVOCATION_ID'):
        print("🕐 systemd boot — USB hazırlığı için 5sn bekleniyor...")
        time.sleep(5)

    # UDP socket: Arduino'dan bagimsiz hemen ac
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(SOCKET_TIMEOUT_SN)
    print(f"📡 Port {UDP_PORT} dinleniyor (UDP)")

    # Arduino baglantisi
    ser = arduino_bagla()
    son_deneme_t = time.time()

    if ser is None:
        print("⏳ Arduino henüz hazır değil, arka planda denemeye devam edilecek...")

    paket_sayac = 0
    durum_yazma_t = time.time()

    try:
        while True:
            now = time.time()

            # Arduino kopuksa periyodik yeniden dene
            if ser is None and (now - son_deneme_t) >= ARDUINO_RETRY_SN:
                ser = arduino_bagla()
                son_deneme_t = now

            # UDP paket bekle
            try:
                data, addr = sock.recvfrom(1024)
                mesaj = data.decode('utf-8', errors='ignore').strip()
                paket_sayac += 1

                if ser is not None:
                    try:
                        ser.write((mesaj + '\n').encode('utf-8'))
                        # Joystick stream log spam'i olmasin diye sadece ozel komutlari yaz
                        if mesaj.startswith("K,") or mesaj.startswith("M,"):
                            print(f"➡️  Arduino: {mesaj}")
                    except (serial.SerialException, OSError) as e:
                        print(f"❌ Arduino yazma hatası, bağlantı kapatılıyor: {e}")
                        try: ser.close()
                        except: pass
                        ser = None
                        son_deneme_t = now

            except socket.timeout:
                pass
            except Exception as e:
                print(f"⚠️  UDP hata: {e}")

            # Periyodik durum
            if (now - durum_yazma_t) >= 10.0:
                durum = "BAĞLI" if ser else "ARDUINO YOK"
                print(f"💓 [{durum}] son {int(now-durum_yazma_t)}sn: {paket_sayac} paket")
                paket_sayac = 0
                durum_yazma_t = now
                # Arduino RDY heartbeat'leri buffer'i doldurmasin
                if ser is not None:
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass

    except KeyboardInterrupt:
        print("\n🛑 Sistem kapatılıyor...")
    finally:
        if ser:
            try: ser.close()
            except: pass
        sock.close()


if __name__ == "__main__":
    main()
