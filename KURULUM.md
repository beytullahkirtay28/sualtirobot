# RÜSUMAT 4 — Kurulum ve Kullanım

## Mimari

```
[Yüzey - Laptop]                    [ROV - Raspberry Pi 5]              [Arduino Uno]
yuzey_istasyonu.py                  rov_beyin.py                        rov_arduino.ino
  • Tkinter GUI                       • UDP dinle (port 5005)             • 6 ESC + 1 servo
  • Joystick (pygame)                 • Arduino seri'ye iletir            • char[] buffer
  • UDP komut yolla    ───────UDP──▶  • by-id symlink                     • Watchdog 2sn
  • TCP video al       ◀───────TCP──  • RDY heartbeat handshake           • RDY her 1sn
  • JPEG decode                       kamera_yayini.py                    • Failsafe 500ms
  • Sade + Gelişmiş                   • Picamera2 → JPEG → TCP            • 3 komut tipi
```

**Veri formatı (UDP/Serial):**
- `sol_x,sol_y,sag_x,sag_y,kol_aci`  — joystick stream
- `M,idx,val`  — tek motor test (idx 1-6, val -1..1)
- `K,angle`  — direkt kol açısı (0-180)

## Pi (Raspberry Pi 5) Kurulumu

### Tek seferlik

```bash
cd ~/Desktop/ROV
git pull
bash scripts/rov-install.sh
```

Bu script:
- Eski `rusumat_beyin` / `rusumat_kamera` servislerini siler
- Yeni `rov-beyin` ve `rov-kamera` servislerini kurar
- Boot'ta otomatik başlatmayı etkinleştirir
- Şimdi başlatır

### Günlük Kullanım

```bash
bash scripts/rov-status.sh    # Sistemin tüm durumu
bash scripts/rov-logs.sh      # Canlı log akışı
bash scripts/rov-restart.sh   # Servisleri yeniden başlat
```

### Manuel Kontrol

```bash
sudo systemctl status rov-beyin
sudo systemctl status rov-kamera
sudo journalctl -u rov-beyin -f       # canlı log
sudo journalctl -u rov-kamera -f      # canlı log
```

## Arduino Yükleme

1. Arduino IDE aç → `rov_arduino.ino`'yu aç
2. Tools → Board: **Arduino Uno**
3. Tools → Port: doğru USB
4. Upload (Ctrl+U)

## Laptop Kurulumu

```bash
pip install pygame opencv-python pillow numpy pyserial
python yuzey_istasyonu.py
```

### .exe Olarak Paketle (Windows, Python kurulu olmasın istersen)

`build.bat` dosyasını **çift tıkla**. Otomatik olarak:
1. PyInstaller ve gerekli paketleri yükler
2. `dist\Rusumat4.exe` ve `dist\config.json` üretir

Sonuç:
- `dist\` klasöründeki **iki dosyayı** (`Rusumat4.exe` + `config.json`) birlikte kopyala
- Python kurulu olmayan Windows makinede çift tıkla çalışır
- IP/port değiştirmek için `config.json` düzenlenir

**Tek dosya yerine klasör istersen** (daha hızlı başlangıç): build.bat içindeki `--onefile` parametresini `--onedir` yap.

## Konfigürasyon

`config.json` ile tüm ayarlar değiştirilir:

```json
{
  "network":  { "pi_ip", "laptop_ip", "udp_port", "video_port" },
  "video":    { "width", "height", "fps", "jpeg_quality" },
  "arduino":  { "baud_rate", "ports" },
  "control":  { "kol_step_joy", "joystick_deadzone", "test_motor_throttle" }
}
```

Pi ve laptop'ta **aynı** dosya kullanılır (kendi alanlarını okurlar).

## Boot Sırası (Beklenen Davranış)

1. **T=0:** LiPo switch ON → Pi açılmaya başlar
2. **T=10-15s:** Pi boot tamam → systemd `rov-beyin` ve `rov-kamera` başlatır
3. **T=15-20s:** rov-beyin Arduino'ya bağlanır → `RDY` yakalar → joystick komutları akmaya hazır
4. **T=20s+:** Laptop'tan `yuzey_istasyonu.py` aç → Bağlan → video gelir, motor/servo kontrol aktif

## Sorun Giderme

| Sorun | Çözüm |
|---|---|
| Motor dönmüyor | `bash scripts/rov-status.sh` → rov-beyin aktif mi? |
| Video gelmiyor | `bash scripts/rov-status.sh` → rov-kamera + kamera donanım kontrol |
| Arduino RDY yok | Arduino'ya en son `.ino` yüklendi mi? Heartbeat satırı var mı? |
| ESC bip yok | LiPo bağlantısı, ESC sinyal kabloları, ortak GND |
| Servis crash loop | `sudo systemctl reset-failed`, sonra `bash scripts/rov-restart.sh` |

## Güvenlik

- **İlk testte propeller çıkar.** Yön doğru mu, hızlanma normal mi gör.
- **Failsafe:** Pi-Arduino bağlantısı kopunca 500ms'de motor durur.
- **Watchdog:** Arduino sketch hang ederse 2sn'de reset olur.
- **Deadzone:** Joystick yaylanma sapması (0.08'in altı) yok sayılır.

## Pin Atamaları

| Arduino Pin | Görev |
|---|---|
| 3  | M1 ön-sol yatay ESC |
| 5  | M2 ön-sağ yatay ESC |
| 6  | M3 arka-sol yatay ESC |
| 9  | M4 arka-sağ yatay ESC |
| 10 | M5 sol dikey ESC |
| 11 | M6 sağ dikey ESC |
| 4  | Kol servo |
