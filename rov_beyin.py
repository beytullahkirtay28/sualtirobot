import socket
import serial
import time
import os

# === AYARLAR ===
UDP_IP = "0.0.0.0"   # tüm ağlardan dinle
UDP_PORT = 5005

# Arduino USB portu (denenir, ilk bulunan kullanılır)
ARDUINO_PORTS = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1', '/dev/ttyACM1']
BAUD_RATE = 115200

# Yeniden bağlanma aralıkları
ARDUINO_RETRY_SN = 3.0   # Arduino kopukken kaç saniyede bir yeniden dene
SOCKET_TIMEOUT_SN = 1.0  # UDP recv timeout (Arduino kontrolü yapabilmek için)

print("=" * 50)
print("RÜSUMAT 4 - BEYİN (UDP -> SERIAL) BAŞLATILIYOR")
print("=" * 50)


def arduino_bagla():
    """Mevcut tüm portları sırayla dene, ilk bulunanı aç."""
    for port in ARDUINO_PORTS:
        if not os.path.exists(port):
            continue
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)  # Arduino reset toparlanma süresi
            ser.reset_input_buffer()
            print(f"✅ Arduino bağlandı: {port}")
            return ser
        except Exception as e:
            print(f"⚠️  {port} açılamadı: {e}")
    return None


def main():
    # --- UDP socket: Arduino'dan bağımsız aç ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(SOCKET_TIMEOUT_SN)
    print(f"📡 Port {UDP_PORT} dinleniyor (UDP)")

    # --- Arduino bağlantısı (ilk açılış, başarısız olsa da devam) ---
    ser = arduino_bagla()
    son_deneme_t = time.time()

    if ser is None:
        print("⏳ Arduino henüz hazır değil, arka planda denenmeye devam edilecek...")

    paket_sayac = 0
    durum_yazma_t = time.time()

    try:
        while True:
            # --- Arduino kopuksa periyodik yeniden dene ---
            now = time.time()
            if ser is None and (now - son_deneme_t) >= ARDUINO_RETRY_SN:
                ser = arduino_bagla()
                son_deneme_t = now

            # --- UDP paket bekle ---
            try:
                data, addr = sock.recvfrom(1024)
                mesaj = data.decode('utf-8', errors='ignore').strip()
                paket_sayac += 1

                # Arduino'ya ilet
                if ser is not None:
                    try:
                        ser.write((mesaj + '\n').encode('utf-8'))
                    except (serial.SerialException, OSError) as e:
                        print(f"❌ Arduino yazma hatası, bağlantı kapatılıyor: {e}")
                        try:
                            ser.close()
                        except Exception:
                            pass
                        ser = None
                        son_deneme_t = now

            except socket.timeout:
                pass  # 1sn'de paket gelmemiş, döngüye devam (Arduino kontrolü için)

            except Exception as e:
                print(f"⚠️  UDP hata: {e}")

            # --- Periyodik durum çıktısı (her 10 sn) ---
            if (now - durum_yazma_t) >= 10.0:
                durum = "BAĞLI" if ser else "ARDUINO YOK"
                print(f"💓 [{durum}] son 10sn: {paket_sayac} paket")
                paket_sayac = 0
                durum_yazma_t = now

    except KeyboardInterrupt:
        print("\n🛑 Sistem kapatılıyor...")
    finally:
        if ser:
            try:
                ser.close()
            except Exception:
                pass
        sock.close()


if __name__ == "__main__":
    main()
