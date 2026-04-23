import socket
import serial
import time

# --- AYARLAR ---
UDP_IP = "0.0.0.0"  # Herkesten dinle
UDP_PORT = 5005     # Laptopun veri gönderdiği port

# Arduino'nun bağlı olduğu USB portu. (Genelde ttyUSB0 veya ttyACM0 olur)
# EĞER HATA VERİRSE burayı '/dev/ttyACM0' olarak değiştir.
ARDUINO_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200

print("="*40)
print("RÜSUMAT 4 - BEYİN (UDP -> SERIAL) BAŞLATILDI")
print("="*40)

# Arduino'ya bağlanmaya çalış
try:
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Arduino'nun kendini resetleyip toparlaması için 2 sn bekle
    print(f"✅ Arduino'ya başarıyla bağlanıldı: {ARDUINO_PORT}")
except Exception as e:
    print(f"❌ Arduino bulunamadı! Lütfen USB kablosunu kontrol et.\nHata: {e}")
    ser = None

# Ağı (Socket) kur
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print(f"📡 Port {UDP_PORT} dinleniyor, komut bekleniyor...")

try:
    while True:
        # Laptoptan gelen kargo paketini (kol verilerini) yakala
        data, addr = sock.recvfrom(1024)
        mesaj = data.decode('utf-8')
        
        # Eğer Arduino bağlıysa, gelen verinin sonuna '\n' (enter) ekleyip Arduino'ya gönder
        if ser:
            veri_paketi = mesaj + '\n'
            ser.write(veri_paketi.encode('utf-8'))
            
            # (İsteğe bağlı) Ekranda akışı görmek istersen alttaki satırın başındaki # işaretini kaldır:
            # print(f"Arduino'ya iletildi -> {mesaj}")

except KeyboardInterrupt:
    print("\nSistem Kapatılıyor...")
finally:
    if ser:
        ser.close()
    sock.close()