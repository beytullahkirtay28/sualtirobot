"""
RÜSUMAT 4 - Yüzey İstasyonu (Laptop GUI)

Özellikler:
- Joystick stream ayrı thread'de çalışır → video bağlanmadan da motor kontrol var
- JPEG decode (Pi'den gelen JPEG frame'leri çözer)
- config.json ile merkezi ayar
- Sade + Gelişmiş panel (13 buton: bağlantı, kamera, motor test, kol kontrol)
- Joystick LB/RB → kol servo, GUI butonları → tüm motor/servo testleri
"""

import tkinter as tk
import socket
import struct
import threading
import time
import json
import os

import cv2
import numpy as np
import pygame
from PIL import Image, ImageTk


# === CONFIG YÜKLE ===
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
try:
    with open(CONFIG_PATH) as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"⚠️ config.json okunamadı: {e}, varsayılanlar kullanılıyor")
    CONFIG = {
        "network": {"pi_ip": "192.168.1.100", "udp_port": 5005, "video_port": 8089},
        "video":   {"width": 640, "height": 480},
        "control": {
            "kol_step_joy": 4, "kol_step_btn": 10,
            "kol_btn_close": 4, "kol_btn_open": 5,
            "joystick_deadzone": 0.08, "test_motor_throttle": 0.4
        }
    }


class Rusumat4Control:
    def __init__(self, window):
        self.window = window
        self.window.title("RÜSUMAT 4 - KONTROL MERKEZİ V5")
        self.window.configure(bg="#1e272e")
        # Geometry video boyutuna göre dinamik (alt panel + başlık için ek alan)
        # V_WIDTH ve V_HEIGHT henüz set edilmedi; aşağıda config okunduktan sonra ayarlanır

        # --- AYARLAR (config'den) ---
        self.PI_IP      = CONFIG['network']['pi_ip']
        self.UDP_PORT   = CONFIG['network']['udp_port']
        self.V_PORT     = CONFIG['network']['video_port']
        self.V_WIDTH    = CONFIG['video']['width']
        self.V_HEIGHT   = CONFIG['video']['height']

        c = CONFIG['control']
        self.kol_aci          = 90
        self.KOL_ADIM_JOY     = c['kol_step_joy']
        self.KOL_ADIM_BTN     = c['kol_step_btn']
        self.KOL_BTN_KAPAT    = c['kol_btn_close']
        self.KOL_BTN_AC       = c['kol_btn_open']
        self.JOY_DEADZONE     = c['joystick_deadzone']
        self.TEST_DEGER       = c['test_motor_throttle']

        # Pencere boyutu video çözünürlüğüne göre dinamik
        # Genişlik: video + 80px kenar boşluğu (min 720)
        # Yükseklik: video + 380px (başlık + bilgi paneli + butonlar)
        win_w = max(720, self.V_WIDTH + 80)
        win_h = self.V_HEIGHT + 380
        self.window.geometry(f"{win_w}x{win_h}")

        # --- DURUM ---
        self.test_motor       = None       # (idx 1..6, val) ya da None
        self.running          = False      # video bağlantı aktif mi
        self.camera_visible   = True
        self.advanced_open    = False
        self.joy              = None
        self.thread_video     = None

        self.sock_kol = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # --- GUI ---
        self._build_ui()

        # --- Arka plan thread'leri (her zaman çalışır) ---
        # Joystick stream + test motor komutları (video bağımsız)
        threading.Thread(target=self._cmd_sender_loop, daemon=True).start()
        # Joystick varlık taraması
        self.check_joystick()

    # ============================================================
    #                          GUI YAPISI
    # ============================================================
    def _build_ui(self):
        # Üst başlık
        tk.Label(self.window, text="RÜSUMAT 4 KAPTAN KÖŞKÜ",
                 font=("Arial", 22, "bold"), bg="#1e272e", fg="#00d8d6").pack(pady=10)

        # Video alanı
        self.canvas = tk.Canvas(self.window, width=self.V_WIDTH, height=self.V_HEIGHT,
                                bg="black", highlightthickness=2,
                                highlightbackground="#575fcf")
        self.canvas.pack()

        # Bilgi paneli (joystick / sistem / kol)
        self.info_frame = tk.Frame(self.window, bg="#1e272e")
        self.info_frame.pack(pady=10)

        self.lbl_joy = tk.Label(self.info_frame, text="🎮 JOYSTICK: ARANIYOR...",
                                font=("Arial", 13, "bold"), bg="#1e272e", fg="#ffa801")
        self.lbl_joy.grid(row=0, column=0, padx=20)

        self.lbl_status = tk.Label(self.info_frame, text="📡 SİSTEM: BEKLİYOR",
                                   font=("Arial", 13, "bold"), bg="#1e272e", fg="#d2dae2")
        self.lbl_status.grid(row=0, column=1, padx=20)

        self.lbl_kol = tk.Label(self.info_frame, text="🦾 KOL: 90°",
                                font=("Arial", 13, "bold"), bg="#1e272e", fg="#ffda79")
        self.lbl_kol.grid(row=0, column=2, padx=20)

        # ========== SADE PANEL (varsayılan) ==========
        self.simple_frame = tk.Frame(self.window, bg="#1e272e")
        self.simple_frame.pack(pady=8)

        tk.Button(self.simple_frame, text="🔄 BAĞLAN / YENİDEN BAĞLAN",
                  command=self.restart_connection,
                  font=("Arial", 12, "bold"), bg="#05c46b", fg="white",
                  width=28, height=2).grid(row=0, column=0, padx=8)

        tk.Button(self.simple_frame, text="📷 KAMERAYI AÇ / KAPA",
                  command=self.toggle_camera,
                  font=("Arial", 12, "bold"), bg="#3742fa", fg="white",
                  width=28, height=2).grid(row=0, column=1, padx=8)

        # Gelişmiş seçenekler link
        self.advanced_link = tk.Label(self.window, text="⚙ Gelişmiş Seçenekler ▼",
                                      font=("Arial", 10, "underline"),
                                      bg="#1e272e", fg="#70a1ff", cursor="hand2")
        self.advanced_link.pack(pady=4)
        self.advanced_link.bind("<Button-1>", lambda e: self.toggle_advanced())

        # ========== GELİŞMİŞ PANEL (gizli) ==========
        self.advanced_frame = tk.Frame(self.window, bg="#1e272e")

        # Satır 1: Bağlantı
        row1 = tk.Frame(self.advanced_frame, bg="#1e272e"); row1.pack(pady=4)
        self._mk_button(row1, "🟢 BAĞLAN",            self.connect,            "#05c46b", 0)
        self._mk_button(row1, "🔴 BAĞLANTIYI KES",    self.disconnect,         "#ff3f34", 1)
        self._mk_button(row1, "🔄 BAĞLANTIYI YİNELE", self.restart_connection, "#ffa502", 2)

        # Satır 2: Kamera + Kol
        row2 = tk.Frame(self.advanced_frame, bg="#1e272e"); row2.pack(pady=4)
        self._mk_button(row2, "📷 KAMERA AÇ/KAPA",     self.toggle_camera, "#3742fa", 0)
        self._mk_button(row2, "🦾 KOL: SIFIRLA (90°)", self.kol_sifirla,   "#7158e2", 1)
        self._mk_button(row2, f"🦾 KOL +{self.KOL_ADIM_BTN}°", self.kol_arttir, "#7158e2", 2)
        self._mk_button(row2, f"🦾 KOL -{self.KOL_ADIM_BTN}°", self.kol_azalt, "#7158e2", 3)

        # Satır 3: Motor test
        tk.Label(self.advanced_frame,
                 text="Motor Testi (basılı tut → ilgili motor düşük güçle çalışır):",
                 font=("Arial", 9), bg="#1e272e", fg="#a4b0be").pack(pady=(8, 2))
        row3 = tk.Frame(self.advanced_frame, bg="#1e272e"); row3.pack(pady=4)
        for i in range(6):
            idx = i + 1
            b = tk.Button(row3, text=f"M{idx}", font=("Arial", 11, "bold"),
                          bg="#485460", fg="white", width=8, height=2,
                          activebackground="#ff6348")
            b.grid(row=0, column=i, padx=4)
            b.bind("<ButtonPress-1>",   lambda e, x=idx: self._test_motor_start(x))
            b.bind("<ButtonRelease-1>", lambda e:        self._test_motor_stop())

        # Satır 4: Kapat
        row4 = tk.Frame(self.advanced_frame, bg="#1e272e"); row4.pack(pady=10)
        tk.Button(row4, text="✖ GELİŞMİŞ SEÇENEKLERİ KAPAT",
                  command=self.toggle_advanced,
                  font=("Arial", 11, "bold"), bg="#57606f", fg="white",
                  width=32, height=2).grid(row=0, column=0)

    def _mk_button(self, parent, text, cmd, color, col):
        b = tk.Button(parent, text=text, command=cmd,
                      font=("Arial", 10, "bold"), bg=color, fg="white",
                      width=22, height=2)
        b.grid(row=0, column=col, padx=4)
        return b

    # ============================================================
    #                       YARDIMCILAR
    # ============================================================
    def _send(self, msg):
        try:
            self.sock_kol.sendto(msg.encode(), (self.PI_IP, self.UDP_PORT))
        except Exception:
            pass

    def _dz(self, v):
        if abs(v) < self.JOY_DEADZONE:
            return 0.0
        sign = 1.0 if v > 0 else -1.0
        scaled = (abs(v) - self.JOY_DEADZONE) / (1.0 - self.JOY_DEADZONE)
        return round(sign * scaled, 3)

    def _update_status(self, text, color):
        self.lbl_status.config(text=text, fg=color)

    def _update_kol_label(self):
        self.lbl_kol.config(text=f"🦾 KOL: {self.kol_aci}°")

    # ============================================================
    #                          JOYSTICK
    # ============================================================
    def check_joystick(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            if self.joy is None:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
            self.lbl_joy.config(text=f"🎮 JOYSTICK: {self.joy.get_name()[:20]}",
                                fg="#0be881")
        else:
            self.joy = None
            self.lbl_joy.config(text="🎮 JOYSTICK: BAĞLI DEĞİL!", fg="#ff3f34")
        self.window.after(1000, self.check_joystick)

    # ============================================================
    #                        BAĞLANTI
    # ============================================================
    def connect(self):
        if self.running:
            self._update_status("📡 ZATEN BAĞLI", "#0be881")
            return
        self._update_status("📡 BAĞLANILIYOR...", "#ffd32a")
        self.window.after(300, self._start_connection)

    def disconnect(self):
        self.running = False
        self._update_status("📡 BAĞLANTI KESİLDİ", "#ff3f34")

    def restart_connection(self):
        self.running = False
        self._update_status("📡 YENİDEN BAĞLANILIYOR...", "#ffd32a")
        self.window.after(1000, self._start_connection)

    def _start_connection(self):
        self.running = True
        self.thread_video = threading.Thread(target=self._video_loop, daemon=True)
        self.thread_video.start()

    # ============================================================
    #                        KAMERA
    # ============================================================
    def toggle_camera(self):
        self.camera_visible = not self.camera_visible
        if self.camera_visible:
            self.canvas.pack(before=self.info_frame)
        else:
            self.canvas.pack_forget()

    def _display_frame(self, pil_img):
        if not self.camera_visible:
            return
        img_tk = ImageTk.PhotoImage(image=pil_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.canvas.image = img_tk   # GC referansı

    # ============================================================
    #                        KOL SERVO
    # ============================================================
    def kol_sifirla(self):  self._kol_set(90)
    def kol_arttir(self):   self._kol_set(self.kol_aci + self.KOL_ADIM_BTN)
    def kol_azalt(self):    self._kol_set(self.kol_aci - self.KOL_ADIM_BTN)

    def _kol_set(self, angle):
        self.kol_aci = max(0, min(180, int(angle)))
        self._update_kol_label()
        self._send(f"K,{self.kol_aci}")

    # ============================================================
    #                      MOTOR TESTİ
    # ============================================================
    def _test_motor_start(self, idx):
        self.test_motor = (idx, self.TEST_DEGER)
        self._update_status(f"🔧 TEST: M{idx}", "#ff6348")

    def _test_motor_stop(self):
        self.test_motor = None
        self._send("M,0,0")
        if self.running:
            self._update_status("📡 BAĞLANTI AKTİF", "#0be881")
        else:
            self._update_status("📡 BEKLİYOR", "#d2dae2")

    # ============================================================
    #                  KOMUT GÖNDERİCİ THREAD
    # ============================================================
    def _cmd_sender_loop(self):
        """30 Hz: test motor varsa onu, yoksa joystick stream'i yollar.
        Video bağlantısından bağımsız çalışır.
        """
        while True:
            if self.test_motor is not None:
                # Motor test modu: joystick yok, sadece test komutu
                idx, val = self.test_motor
                self._send(f"M,{idx},{val}")

            elif self.joy is not None:
                # Normal joystick stream
                try:
                    pygame.event.pump()
                    sol_x = self._dz(self.joy.get_axis(0))
                    sol_y = self._dz(self.joy.get_axis(1))
                    sag_x = self._dz(self.joy.get_axis(2))
                    sag_y = self._dz(self.joy.get_axis(3))

                    # Kol LB/RB
                    if self.joy.get_button(self.KOL_BTN_KAPAT):
                        self.kol_aci = max(0, self.kol_aci - self.KOL_ADIM_JOY)
                    if self.joy.get_button(self.KOL_BTN_AC):
                        self.kol_aci = min(180, self.kol_aci + self.KOL_ADIM_JOY)

                    # GUI label güncelle (thread-safe)
                    self.window.after(0, self._update_kol_label)

                    cmd = f"{sol_x},{sol_y},{sag_x},{sag_y},{self.kol_aci}"
                    self._send(cmd)
                except Exception:
                    pass

            time.sleep(0.033)   # ~30 Hz

    # ============================================================
    #                  GELİŞMİŞ PANEL TOGGLE
    # ============================================================
    def toggle_advanced(self):
        if self.advanced_open:
            self.advanced_frame.pack_forget()
            self.simple_frame.pack(pady=8, before=self.advanced_link)
            self.advanced_link.config(text="⚙ Gelişmiş Seçenekler ▼")
        else:
            self.simple_frame.pack_forget()
            self.advanced_frame.pack(pady=8, before=self.advanced_link)
            self.advanced_link.config(text="⚙ Gelişmiş Seçenekler ▲")
        self.advanced_open = not self.advanced_open

    # ============================================================
    #                   VIDEO ALMA THREAD'i
    # ============================================================
    def _video_loop(self):
        """Pi'den JPEG sıkıştırılmış frame'leri TCP üzerinden alır,
        decode edip canvas'a basar.
        """
        v_server = None
        conn = None
        try:
            v_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            v_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            v_server.bind(('0.0.0.0', self.V_PORT))
            v_server.listen(1)
            v_server.settimeout(5.0)

            conn, addr = v_server.accept()
            conn.settimeout(3.0)
            self.window.after(0, lambda: self._update_status("📡 BAĞLANTI AKTİF",
                                                              "#0be881"))

            data = b""
            payload_size = struct.calcsize("Q")

            while self.running:
                # Boyut prefix'i oku
                while len(data) < payload_size:
                    packet = conn.recv(64 * 1024)
                    if not packet:
                        raise Exception("Bağlantı kapandı (boş paket)")
                    data += packet

                msg_size = struct.unpack("Q", data[:payload_size])[0]
                data = data[payload_size:]

                # JPEG verisini topla
                while len(data) < msg_size:
                    packet = conn.recv(64 * 1024)
                    if not packet:
                        raise Exception("Bağlantı kapandı (frame ortasında)")
                    data += packet

                jpeg_bytes = data[:msg_size]
                data = data[msg_size:]

                # JPEG decode → BGR numpy array
                arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame_bgr is None:
                    continue

                # BGR → RGB → PIL
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                # Ana thread'de canvas'a bas
                self.window.after(0, lambda i=pil_img: self._display_frame(i))

        except Exception as e:
            if self.running:
                self.window.after(0, lambda:
                    self._update_status(f"📡 BAĞLANTI KOPTU: {type(e).__name__}",
                                        "#ff3f34"))
        finally:
            try: conn.close()
            except: pass
            try: v_server.close()
            except: pass


if __name__ == "__main__":
    root = tk.Tk()
    app = Rusumat4Control(root)
    root.mainloop()
