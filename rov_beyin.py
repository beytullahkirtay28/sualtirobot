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
    """Mevcut tüm portları sırayla dene, RDY heartbeat'ini bekleyen ilk portu aç.
    DTR/RTS devre disi: port acmak Arduino'yu resetlemez, mevcut sketch devam eder.
    """
    for port in ARDUINO_PORTS:
        if not os.path.exists(port):
            continue
        try:
            # DTR/RTS'i Arduino reset etmesin diye onceden devre disi birak
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = BAUD_RATE
            ser.timeout = 1
            ser.dtr = False
            ser.rts = False
            ser.open()

            # Arduino her 1 saniyede bir "RDY\n" gönderir (heartbeat).
            # Reset olmadigi icin Pi acar acmaz heartbeat'i yakalar.
            print(f"⏳ {port} açıldı (DTR/RTS off), Arduino RDY sinyali bekleniyor...")
            deadline = time.time() + 4.0   # max 4sn bekle (heartbeat 1sn'lik)
            while time.time() < deadline:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line == "RDY":
                    print(f"✅ Arduino hazır: {port}")
                    ser.reset_input_buffer()
                    return ser

            print(f"⚠️  {port} açıldı ama RDY gelmedi, yine de kullanılıyor")
            return ser

        except Exception as e:
            print(f"⚠️  {port} açılamadı: {e}")
    return None


def main():
    # systemd ile boot sirasinda baslatilmissa, USB/udev hazirligi icin bekle
    if os.environ.get('INVOCATION_ID'):
        print("🕐 systemd boot moda algılandı, USB hazırlığı için 5sn bekleniyor...")
        time.sleep(5)

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
                        # Servo/test komutlari (joystick stream'i log spam yapmasın diye filtre)
                        if mesaj.startswith("K,") or mesaj.startswith("M,"):
                            print(f"➡️  Arduino'ya gönderildi: {mesaj}")
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
                # Arduino heartbeat'leri (RDY) buffer doldurmasin
                if ser is not None:
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass

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
