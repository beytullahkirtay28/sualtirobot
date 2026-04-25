import tkinter as tk
import cv2, socket, struct, pickle, threading, pygame
from PIL import Image, ImageTk
import time

class Rusumat4Control:
    def __init__(self, window):
        self.window = window
        self.window.title("RÜSUMAT 4 - KONTROL MERKEZİ V4")
        self.window.geometry("960x900")
        self.window.configure(bg="#1e272e")

        # --- AYARLAR ---
        self.PI_IP = "192.168.1.100"
        self.UDP_PORT = 5005
        self.V_PORT = 8089

        # Joystick / kol
        self.kol_aci = 90
        self.KOL_ADIM_JOY = 2          # joystick LB/RB için derece
        self.KOL_ADIM_BTN = 5          # GUI butonları için derece
        self.KOL_BTN_KAPAT = 4         # joystick LB
        self.KOL_BTN_AC = 5            # joystick RB

        # Motor test (basıldığı sürece ilgili motor çalışır)
        self.TEST_DEGER = 0.3          # test motor throttle değeri (-1..1)
        self.test_motor = None         # (idx 1..6, val) ya da None

        # Durum
        self.running = False
        self.camera_visible = True
        self.advanced_open = False
        self.sock_kol = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.joy = None
        self.thread = None

        # Üst Başlık
        tk.Label(window, text="RÜSUMAT 4 KAPTAN KÖŞKÜ", font=("Arial", 22, "bold"),
                 bg="#1e272e", fg="#00d8d6").pack(pady=10)

        # Video Ekranı
        self.canvas = tk.Canvas(window, width=640, height=480, bg="black",
                                highlightthickness=2, highlightbackground="#575fcf")
        self.canvas.pack()

        # Bilgi Paneli
        self.info_frame = tk.Frame(window, bg="#1e272e")
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

        # ==================== SADE PANEL (varsayılan: 2 buton) ====================
        self.simple_frame = tk.Frame(window, bg="#1e272e")
        self.simple_frame.pack(pady=8)

        self.btn_simple_baglan = tk.Button(
            self.simple_frame, text="🔄 BAĞLAN / YENİDEN BAĞLAN",
            command=self.restart_connection,
            font=("Arial", 12, "bold"), bg="#05c46b", fg="white", width=28, height=2)
        self.btn_simple_baglan.grid(row=0, column=0, padx=8)

        self.btn_simple_kamera = tk.Button(
            self.simple_frame, text="📷 KAMERAYI AÇ / KAPA",
            command=self.toggle_camera,
            font=("Arial", 12, "bold"), bg="#3742fa", fg="white", width=28, height=2)
        self.btn_simple_kamera.grid(row=0, column=1, padx=8)

        # Gelişmiş seçenekler bağlantısı (link tarzı yazı)
        self.advanced_link = tk.Label(window, text="⚙ Gelişmiş Seçenekler ▼",
                                      font=("Arial", 10, "underline"),
                                      bg="#1e272e", fg="#70a1ff", cursor="hand2")
        self.advanced_link.pack(pady=4)
        self.advanced_link.bind("<Button-1>", lambda e: self.toggle_advanced())

        # ==================== GELİŞMİŞ PANEL (gizli) ====================
        self.advanced_frame = tk.Frame(window, bg="#1e272e")
        # pack edilmedi (varsayılan: gizli)

        # Satır 1: Bağlantı butonları (3 ad)
        row1 = tk.Frame(self.advanced_frame, bg="#1e272e")
        row1.pack(pady=4)
        self._mk_button(row1, "🟢 BAĞLAN",         self.connect,           "#05c46b", 0)
        self._mk_button(row1, "🔴 BAĞLANTIYI KES", self.disconnect,        "#ff3f34", 1)
        self._mk_button(row1, "🔄 BAĞLANTIYI YİNELE", self.restart_connection, "#ffa502", 2)

        # Satır 2: Kamera + Kol kontrol (4 ad)
        row2 = tk.Frame(self.advanced_frame, bg="#1e272e")
        row2.pack(pady=4)
        self._mk_button(row2, "📷 KAMERA AÇ/KAPA",   self.toggle_camera,    "#3742fa", 0)
        self._mk_button(row2, "🦾 KOL: SIFIRLA (90°)", self.kol_sifirla,    "#7158e2", 1)
        self._mk_button(row2, "🦾 KOL +5°",           self.kol_arttir,     "#7158e2", 2)
        self._mk_button(row2, "🦾 KOL -5°",           self.kol_azalt,      "#7158e2", 3)

        # Satır 3: Motor test (6 ad — basılı tut)
        tk.Label(self.advanced_frame,
                 text="Motor Testi (basılı tut → ilgili motor düşük güçle çalışır):",
                 font=("Arial", 9), bg="#1e272e", fg="#a4b0be").pack(pady=(8, 2))
        row3 = tk.Frame(self.advanced_frame, bg="#1e272e")
        row3.pack(pady=4)
        for i in range(6):
            idx = i + 1
            b = tk.Button(row3, text=f"M{idx}", font=("Arial", 11, "bold"),
                          bg="#485460", fg="white", width=8, height=2,
                          activebackground="#ff6348")
            b.grid(row=0, column=i, padx=4)
            b.bind("<ButtonPress-1>",   lambda e, x=idx: self._test_motor_start(x))
            b.bind("<ButtonRelease-1>", lambda e:        self._test_motor_stop())

        # Satır 4: Gelişmiş kapat
        row4 = tk.Frame(self.advanced_frame, bg="#1e272e")
        row4.pack(pady=10)
        tk.Button(row4, text="✖ GELİŞMİŞ SEÇENEKLERİ KAPAT",
                  command=self.toggle_advanced,
                  font=("Arial", 11, "bold"), bg="#57606f", fg="white",
                  width=32, height=2).grid(row=0, column=0)

        # Periyodik komut göndericisi (test motor için, bağlantıdan bağımsız)
        threading.Thread(target=self._cmd_sender_loop, daemon=True).start()

        # Joystick taraması
        self.check_joystick()

    # ----------------------------- Yardımcılar -----------------------------
    def _mk_button(self, parent, text, cmd, color, col):
        b = tk.Button(parent, text=text, command=cmd,
                      font=("Arial", 10, "bold"), bg=color, fg="white",
                      width=22, height=2)
        b.grid(row=0, column=col, padx=4)
        return b

    def _send(self, msg):
        try:
            self.sock_kol.sendto(msg.encode(), (self.PI_IP, self.UDP_PORT))
        except Exception:
            pass

    # ----------------------------- Joystick -----------------------------
    def check_joystick(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            if self.joy is None:
                self.joy = pygame.joystick.Joystick(0)
                self.joy.init()
            self.lbl_joy.config(text="🎮 JOYSTICK: BAĞLI", fg="#0be881")
        else:
            self.joy = None
            self.lbl_joy.config(text="🎮 JOYSTICK: BAĞLI DEĞİL!", fg="#ff3f34")
        self.window.after(1000, self.check_joystick)

    # ----------------------------- Bağlantı -----------------------------
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
        self.thread = threading.Thread(target=self.network_loop, daemon=True)
        self.thread.start()

    def _update_status(self, text, color):
        self.lbl_status.config(text=text, fg=color)

    # ----------------------------- Kamera -----------------------------
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
        self.canvas.image = img_tk

    # ----------------------------- Kol Servo -----------------------------
    def kol_sifirla(self):
        self._kol_set(90)

    def kol_arttir(self):
        self._kol_set(self.kol_aci + self.KOL_ADIM_BTN)

    def kol_azalt(self):
        self._kol_set(self.kol_aci - self.KOL_ADIM_BTN)

    def _kol_set(self, angle):
        self.kol_aci = max(0, min(180, int(angle)))
        self.lbl_kol.config(text=f"🦾 KOL: {self.kol_aci}°")
        self._send(f"K,{self.kol_aci}")

    # ----------------------------- Motor Testi -----------------------------
    def _test_motor_start(self, idx):
        self.test_motor = (idx, self.TEST_DEGER)
        self._update_status(f"🔧 TEST: M{idx}", "#ff6348")

    def _test_motor_stop(self):
        self.test_motor = None
        self._send("M,0,0")   # tüm motorları neutral
        if self.running:
            self._update_status("📡 BAĞLANTI AKTİF", "#0be881")
        else:
            self._update_status("📡 BEKLİYOR", "#d2dae2")

    def _cmd_sender_loop(self):
        # 20 Hz: test motor komutu yolla. Bağlantıdan bağımsız çalışır.
        while True:
            if self.test_motor is not None:
                idx, val = self.test_motor
                self._send(f"M,{idx},{val}")
            time.sleep(0.05)

    # ----------------------------- Gelişmiş Toggle -----------------------------
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

    # ----------------------------- Network Loop -----------------------------
    def network_loop(self):
        conn = None
        v_server = None
        try:
            v_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            v_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            v_server.bind(('0.0.0.0', self.V_PORT))
            v_server.listen(1)
            v_server.settimeout(3.0)

            conn, addr = v_server.accept()
            conn.settimeout(2.0)
            self.window.after(0, lambda: self._update_status("📡 BAĞLANTI AKTİF", "#0be881"))

            data = b""
            payload_size = struct.calcsize("Q")

            while self.running:
                # --- VİDEO ALIMI ---
                while len(data) < payload_size:
                    packet = conn.recv(4*1024)
                    if not packet: raise Exception("Bağlantı Koptu")
                    data += packet

                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]

                while len(data) < msg_size:
                    data += conn.recv(4*1024)

                frame_data = data[:msg_size]
                data = data[msg_size:]
                frame = pickle.loads(frame_data)

                # --- JOYSTICK STREAM (test modunda susar) ---
                if self.joy and self.test_motor is None:
                    pygame.event.pump()
                    sol_x = round(self.joy.get_axis(0), 2)
                    sol_y = round(self.joy.get_axis(1), 2)
                    sag_x = round(self.joy.get_axis(2), 2)
                    sag_y = round(self.joy.get_axis(3), 2)

                    try:
                        if self.joy.get_button(self.KOL_BTN_KAPAT):
                            self.kol_aci = max(0, self.kol_aci - self.KOL_ADIM_JOY)
                        if self.joy.get_button(self.KOL_BTN_AC):
                            self.kol_aci = min(180, self.kol_aci + self.KOL_ADIM_JOY)
                    except Exception:
                        pass
                    self.window.after(0, lambda a=self.kol_aci: self.lbl_kol.config(text=f"🦾 KOL: {a}°"))

                    cmd = f"{sol_x},{sol_y},{sag_x},{sag_y},{self.kol_aci}"
                    self._send(cmd)

                # --- GÖRÜNTÜYÜ EKRANA BAS ---
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img)
                self.window.after(0, lambda i=pil_img: self._display_frame(i))

        except Exception as e:
            if self.running:
                self.window.after(0, lambda: self._update_status("📡 BAĞLANTI KOPTU (DONDU)", "#ff3f34"))
        finally:
            try: conn.close()
            except: pass
            try: v_server.close()
            except: pass

root = tk.Tk()
app = Rusumat4Control(root)
root.mainloop()
