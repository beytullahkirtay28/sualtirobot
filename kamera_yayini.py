"""
RÜSUMAT 4 - Kamera Yayını
Pi Camera → JPEG sıkıştırma → TCP üzerinden laptop'a gönderim.

Özellikler:
- JPEG sıkıştırma (raw'a göre 10-15x daha az bant genişliği)
- FPS sınırı (CPU'yu zorlamaz)
- Otomatik kamera yeniden başlatma (kamera bozulursa)
- Otomatik laptop'a yeniden bağlanma (bağlantı koparsa)
- Connect timeout (laptop yoksa hızlı başarısızlık)
- Asla exit etmez → systemd restart loop'una düşmez
"""

import socket
import struct
import time
import json
import os
import sys

import cv2
import numpy as np

# --- CONFIG YÜKLE ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
try:
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"❌ config.json okunamadı: {e}")
    print("   Varsayılan ayarlar kullanılıyor.")
    CONFIG = {
        "network": {"laptop_ip": "192.168.1.10", "video_port": 8089},
        "video":   {"width": 640, "height": 480, "fps": 30, "jpeg_quality": 75}
    }

LAPTOP_IP    = CONFIG['network']['laptop_ip']
VIDEO_PORT   = CONFIG['network']['video_port']
WIDTH        = CONFIG['video']['width']
HEIGHT       = CONFIG['video']['height']
FPS          = CONFIG['video']['fps']
JPEG_QUALITY = CONFIG['video']['jpeg_quality']

FRAME_INTERVAL    = 1.0 / FPS
CONNECT_TIMEOUT   = 3.0     # laptop'a bağlanma timeout
RECONNECT_WAIT    = 2.0     # bağlantı kopunca bekleme
CAMERA_RETRY_WAIT = 5.0     # kamera açılamadığında bekleme

print("=" * 50)
print("RÜSUMAT 4 - KAMERA YAYIN BAŞLATILIYOR")
print(f"Hedef: {LAPTOP_IP}:{VIDEO_PORT} | {WIDTH}x{HEIGHT} @ {FPS}fps | JPEG q{JPEG_QUALITY}")
print("=" * 50)


def kamera_baslat():
    """Picamera2'yi başlat. Başarısızsa None döner."""
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        config = cam.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"}
        )
        cam.configure(config)
        cam.start()
        time.sleep(0.5)   # warmup
        print(f"✅ Kamera hazır")
        return cam
    except Exception as e:
        print(f"❌ Kamera başlatılamadı: {e}")
        return None


def kamera_kapat(cam):
    """Kamerayı düzgünce kapat."""
    if cam is None:
        return
    try:
        cam.stop()
        cam.close()
    except Exception:
        pass


def laptopa_baglan():
    """Laptop'a TCP bağlantısı kur. Başarısızsa None döner."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(CONNECT_TIMEOUT)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        sock.connect((LAPTOP_IP, VIDEO_PORT))
        sock.settimeout(None)   # data göndermek için blocking moda dön
        # TCP keep-alive (kopuk bağlantıyı algıla)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        print(f"✅ Laptop bağlı: {LAPTOP_IP}:{VIDEO_PORT}")
        return sock
    except Exception as e:
        try: sock.close()
        except: pass
        return None


def main():
    cam = None
    last_frame_t = 0.0
    frame_sayac = 0
    durum_t = time.time()

    while True:
        # --- 1) Kamera kontrolü ---
        if cam is None:
            cam = kamera_baslat()
            if cam is None:
                time.sleep(CAMERA_RETRY_WAIT)
                continue

        # --- 2) Laptop'a bağlan ---
        sock = laptopa_baglan()
        if sock is None:
            print(f"⏳ Laptop bekleniyor ({LAPTOP_IP}:{VIDEO_PORT})...")
            time.sleep(RECONNECT_WAIT)
            continue

        # --- 3) Frame gönderim döngüsü ---
        try:
            while True:
                # FPS sınırı
                now = time.time()
                elapsed = now - last_frame_t
                if elapsed < FRAME_INTERVAL:
                    time.sleep(FRAME_INTERVAL - elapsed)
                last_frame_t = time.time()

                # Frame yakala (RGB888 → cv2 BGR'a çevir)
                frame = cam.capture_array()
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # JPEG sıkıştır
                ok, jpeg = cv2.imencode(
                    '.jpg', frame_bgr,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if not ok:
                    continue

                jpeg_bytes = jpeg.tobytes()
                msg = struct.pack("Q", len(jpeg_bytes)) + jpeg_bytes
                sock.sendall(msg)

                frame_sayac += 1

                # Periyodik durum
                if (now - durum_t) >= 10.0:
                    fps_ger = frame_sayac / (now - durum_t)
                    print(f"💓 son {int(now-durum_t)}sn: {frame_sayac} frame "
                          f"(~{fps_ger:.1f} FPS)")
                    frame_sayac = 0
                    durum_t = now

        except (BrokenPipeError, ConnectionResetError, OSError, socket.error) as e:
            print(f"❌ Bağlantı koptu: {e}")
        except Exception as e:
            # Beklenmedik hata: belki kamera bozuldu, sıfırla
            print(f"⚠️  Beklenmedik hata: {e}")
            kamera_kapat(cam)
            cam = None
        finally:
            try: sock.close()
            except: pass

        time.sleep(RECONNECT_WAIT)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Kamera yayın kapatılıyor...")
    except Exception as e:
        print(f"💥 Beklenmedik kritik hata: {e}")
        # systemd Restart=always otomatik tekrar başlatır
        sys.exit(1)
