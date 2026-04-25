import tkinter as tk
import cv2, socket, struct, pickle, threading, pygame
from PIL import Image, ImageTk
import time

class Rusumat4Control:
    def __init__(self, window):
        self.window = window
        self.window.title("RÜSUMAT 4 - KONTROL MERKEZİ V3")
        self.window.geometry("900x750")
        self.window.configure(bg="#1e272e")

        # --- AYARLAR ---
        self.PI_IP = "192.168.1.100"
        self.UDP_PORT = 5005
        self.V_PORT = 8089

        # Arayüz Üst Başlık
        tk.Label(window, text="RÜSUMAT 4 KAPTAN KÖŞKÜ", font=("Arial", 22, "bold"), bg="#1e272e", fg="#00d8d6").pack(pady=10)

        # Video Ekranı
        self.canvas = tk.Canvas(window, width=640, height=480, bg="black", highlightthickness=2, highlightbackground="#575fcf")
        self.canvas.pack()

        # Bilgi Paneli (Durum Çubuğu)
        self.info_frame = tk.Frame(window, bg="#1e272e")
        self.info_frame.pack(pady=15)

        self.lbl_joy = tk.Label(self.info_frame, text="🎮 JOYSTICK: ARANIYOR...", font=("Arial", 14, "bold"), bg="#1e272e", fg="#ffa801")
        self.lbl_joy.grid(row=0, column=0, padx=30)

        self.lbl_status = tk.Label(self.info_frame, text="📡 SİSTEM: BEKLİYOR", font=("Arial", 14, "bold"), bg="#1e272e", fg="#d2dae2")
        self.lbl_status.grid(row=0, column=1, padx=30)

        self.lbl_kol = tk.Label(self.info_frame, text="🦾 KOL: 90°", font=("Arial", 14, "bold"), bg="#1e272e", fg="#ffda79")
        self.lbl_kol.grid(row=0, column=2, padx=30)

        # Butonlar
        self.btn_frame = tk.Frame(window, bg="#1e272e")
        self.btn_frame.pack(pady=10)

        self.btn_connect = tk.Button(self.btn_frame, text="🔄 BAĞLANTIYI KUR / YENİLE", command=self.restart_connection, font=("Arial", 12, "bold"), bg="#05c46b", fg="white", width=30, height=2)
        self.btn_connect.grid(row=0, column=0)

        # Arka Plan Değişkenleri
        self.running = False
        self.sock_kol = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.joy = None
        self.thread = None

        # Kol servo durumu (0..180)
        self.kol_aci = 90
        self.KOL_ADIM = 2          # her okumada artış (derece)
        self.KOL_BTN_KAPAT = 4     # LB
        self.KOL_BTN_AC = 5        # RB
        
        # Joystick kontrolünü sürekli yapacak fonksiyonu başlat
        self.check_joystick()

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
        
        # Saniyede bir kolu kontrol etmeye devam et
        self.window.after(1000, self.check_joystick)

    def restart_connection(self):
        self.running = False # Eski bağlantıyı öldür
        self.btn_connect.config(state="disabled")
        self.lbl_status.config(text="📡 YENİDEN BAĞLANILIYOR...", fg="#ffd32a")
        self.window.after(1000, self._start_connection) # UI donmadan 1 sn bekle

    def _start_connection(self):
        self.running = True
        self.btn_connect.config(state="normal")
        self.thread = threading.Thread(target=self.network_loop, daemon=True)
        self.thread.start()

    def _update_status(self, text, color):
        self.lbl_status.config(text=text, fg=color)

    def _display_frame(self, pil_img):
        img_tk = ImageTk.PhotoImage(image=pil_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.canvas.image = img_tk

    def network_loop(self):
        conn = None
        v_server = None
        try:
            # Video Sunucusunu Başlat
            v_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            v_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            v_server.bind(('0.0.0.0', self.V_PORT))
            v_server.listen(1)
            v_server.settimeout(3.0) # 3 saniye bağlantı gelmezse hata ver

            conn, addr = v_server.accept()
            conn.settimeout(2.0) # Yayın 2 saniye donarsa bağlantıyı kes
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

                # --- KOL VERİSİ GÖNDERİMİ ---
                if self.joy:
                    pygame.event.pump()
                    sol_x = round(self.joy.get_axis(0), 2)
                    sol_y = round(self.joy.get_axis(1), 2)
                    sag_x = round(self.joy.get_axis(2), 2)
                    sag_y = round(self.joy.get_axis(3), 2)

                    # Robot kolu servosu (LB=kapat, RB=aç)
                    try:
                        if self.joy.get_button(self.KOL_BTN_KAPAT):
                            self.kol_aci = max(0, self.kol_aci - self.KOL_ADIM)
                        if self.joy.get_button(self.KOL_BTN_AC):
                            self.kol_aci = min(180, self.kol_aci + self.KOL_ADIM)
                    except Exception:
                        pass
                    self.window.after(0, lambda a=self.kol_aci: self.lbl_kol.config(text=f"🦾 KOL: {a}°"))

                    cmd = f"{sol_x},{sol_y},{sag_x},{sag_y},{self.kol_aci}"
                    self.sock_kol.sendto(cmd.encode(), (self.PI_IP, self.UDP_PORT))

                # --- GÖRÜNTÜYÜ EKRANA BAS (ana thread'de güvenli) ---
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