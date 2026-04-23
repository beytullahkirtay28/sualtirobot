import socket

# --- AĞ (NETWORK) AYARLARI ---
UDP_IP = "0.0.0.0"  # 0.0.0.0 demek "Bana gelen bütün ağlardan (kablo/wifi) dinle" demektir.
UDP_PORT = 5005     # Laptop ile aynı kapı numarasını dinliyoruz

# Havada uçuşan kargoları yakalayacak olan ağımızı (socket) kuruyoruz
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Dinleme kapısını açıyoruz
sock.bind((UDP_IP, UDP_PORT))

print("="*40)
print(f"SİSTEM AKTİF - Port {UDP_PORT} Dinleniyor...")
print("Yüzey İstasyonundan komut bekleniyor... (Çıkış: CTRL+C)")
print("="*40)

try:
    while True:
        # Gelen veriyi (data) ve gönderenin adresini (addr) yakala
        # 1024, tek seferde alınabilecek maksimum paket boyutudur (bizim için fazlasıyla yeterli)
        data, addr = sock.recvfrom(1024) 
        
        # Gelen şifreli veriyi bizim okuyabileceğimiz metin (String) formatına çevir
        mesaj = data.decode('utf-8')
        
        print(f"Yakaladı! -> {mesaj}")

except KeyboardInterrupt:
    print("\nDinleme sonlandırıldı.")
    sock.close()