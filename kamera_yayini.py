import cv2
import socket
import struct
import pickle
import time
from picamera2 import Picamera2

# --- AYARLAR ---
LAPTOP_IP = "192.168.1.10"
PORT = 8089

print("Rüsumat 4: Kamera donanımı hazırlanıyor...")

# Kamerayı bir kez başlatıyoruz ki sürekli aç/kapa yapıp yorulmasın
try:
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": (640, 480)})
    picam2.configure(config)
    picam2.start()
except Exception as e:
    print(f"Kamera başlatılamadı: {e}")
    exit()

# ANA DÖNGÜ (Koparsa veya bağlanamazsa hep buraya dönecek)
while True:
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"📡 {LAPTOP_IP}:{PORT} adresi aranıyor...")
    
    try:
        # Laptop kapısını çal
        client_socket.connect((LAPTOP_IP, PORT))
        print("✅ Yüzey İstasyonu (Laptop) bulundu! Görüntü aktarımı başlıyor...")
        
        # GÖRÜNTÜ GÖNDERME DÖNGÜSÜ
        while True:
            frame = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            data = pickle.dumps(frame_bgr)
            message = struct.pack("Q", len(data)) + data
            client_socket.sendall(message)
            
    except Exception as e:
        print(f"❌ Bağlantı yok veya koptu. 2 saniye sonra tekrar denenecek...")
        try:
            client_socket.close() # Bozuk bağlantıyı temizle
        except:
            pass
        time.sleep(2) # 2 saniye bekle ve en başa dönüp tekrar kapıyı çal