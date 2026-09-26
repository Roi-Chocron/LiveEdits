#!/usr/bin/env python3
"""
LiveEdits Streamer Client Desktop GUI (Desktop Native App)
-----------------------------------------------------------
אפליקציית דסקטופ עצמאית (GUI) עבור הסטרימר עם ממשק Stream Deck מובנה.
- מתחברת ישירות ל-OBS Studio המקומי דרך WebSocket (4455).
- כוללת ממשק גרפי מלא של כפתורי Stream Deck (ריאקשן, דרמה, גיימינג, חפיפה, השהייה, סיום).
- מעלה אוטומטית את קובץ ההקלטה לשרת הענן בסיום.
- מאפשרת הגדרת קאנבס 4K בלחיצה אחת.
"""

import os
import sys
import time
import socket
import json
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import requests

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "server_url": "https://liveedits.roi-chocron7.workers.dev",
    "obs_host": "127.0.0.1",
    "obs_port": 4455,
    "obs_password": "",
    "auto_upload": True
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG

config = load_config()

class OBSManager:
    def __init__(self, host="127.0.0.1", port=4455, password=""):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        self.is_recording = False
        self.start_time = None
        self.current_action = None

    def is_listening(self):
        try:
            with socket.create_connection((self.host, self.port), timeout=0.3):
                return True
        except Exception:
            return False

    def connect(self):
        if not self.is_listening():
            return False, "OBS אינו פועל או ש-WebSocket אינו מופעל בפורט 4455"
        try:
            import obsws_python as obs
            self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password if self.password else None)
            return True, "מחובר בהצלחה ל-OBS Studio"
        except Exception as e:
            self.client = None
            return False, str(e)

    def set_4k_canvas(self):
        if not self.client:
            ok, msg = self.connect()
            if not ok:
                return False, msg
        try:
            settings = self.client.get_video_settings()
            fps_num = getattr(settings, 'fps_numerator', 60)
            fps_den = getattr(settings, 'fps_denominator', 1)
            self.client.set_video_settings(fps_num, fps_den, 3840, 2160, 3840, 2160)
            return True, "קאנבס OBS הוגדר בהצלחה ל-4K Grid (3840x2160)!"
        except Exception as e:
            return False, str(e)

    def start_record(self, action_name):
        if not self.client:
            ok, msg = self.connect()
            if not ok:
                raise Exception(msg)
        try:
            self.set_4k_canvas()
        except Exception:
            pass
        self.client.start_record()
        self.is_recording = True
        self.start_time = datetime.now()
        self.current_action = action_name

    def toggle_pause(self):
        if not self.client:
            raise Exception("אין חיבור ל-OBS")
        self.client.toggle_record_pause()

    def stop_record(self):
        if not self.client:
            raise Exception("אין חיבור ל-OBS")
        res = self.client.stop_record()
        self.is_recording = False
        file_path = getattr(res, 'output_path', '')
        file_name = os.path.basename(file_path) if file_path else 'recording.mp4'

        dur_str = "00:00:00"
        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.start_time:
            dur_sec = int((datetime.now() - self.start_time).total_seconds())
            dur_str = f"{dur_sec // 3600:02d}:{(dur_sec % 3600) // 60:02d}:{dur_sec % 60:02d}"
            formatted_date = self.start_time.strftime("%Y-%m-%d %H:%M:%S")

        action_name = self.current_action or "ידני"
        self.start_time = None
        self.current_action = None

        return {
            "id": f"obs-{int(time.time())}",
            "file_name": file_name,
            "file_path": file_path,
            "button_used": action_name,
            "date_time": formatted_date,
            "duration": dur_str
        }

class StreamDeckApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiveEdits - Stream Deck Client")
        self.geometry("780x620")
        self.configure(bg="#0b0f19")
        self.resizable(False, False)

        self.obs = OBSManager(
            host=config.get("obs_host", "127.0.0.1"),
            port=config.get("obs_port", 4455),
            password=config.get("obs_password", "")
        )

        self.create_widgets()
        self.check_obs_status_async()

    def create_widgets(self):
        # Header Frame
        header = tk.Frame(self, bg="#111827", height=80)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="🎬 LiveEdits Stream Deck Client",
            font=("Segoe UI", 16, "bold"),
            fg="#ffffff",
            bg="#111827"
        )
        title_lbl.pack(side=tk.LEFT, padx=20, pady=15)

        btn_4k = tk.Button(
            header,
            text="⚙️ הגדר קאנבס 4K",
            font=("Segoe UI", 10, "bold"),
            bg="#059669",
            fg="#ffffff",
            activebackground="#047857",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=self.on_set_4k
        )
        btn_4k.pack(side=tk.RIGHT, padx=20, pady=15)

        # Status Bar
        self.status_var = tk.StringVar(value="בודק חיבור ל-OBS...")
        status_bar = tk.Label(
            self,
            textvariable=self.status_var,
            font=("Segoe UI", 11, "bold"),
            fg="#38bdf8",
            bg="#0b0f19",
            pady=10
        )
        status_bar.pack(fill=tk.X)

        # Grid of Deck Buttons
        grid_frame = tk.Frame(self, bg="#0b0f19")
        grid_frame.pack(expand=True, fill=tk.BOTH, padx=40, pady=15)

        buttons_def = [
            ("😂 ריאקשן", "#4f46e5", "#4338ca", lambda: self.on_action("ריאקשן")),
            ("🎭 דרמה", "#d97706", "#b45309", lambda: self.on_action("דרמה")),
            ("🎮 גיימינג", "#059669", "#047857", lambda: self.on_action("גיימינג")),
            ("📑 חפיפה", "#7c3aed", "#6d28d9", lambda: self.on_action("חפיפה")),
            ("✨ אחר", "#475569", "#334155", lambda: self.on_action("אחר")),
            ("⏸️ השהייה", "#ea580c", "#c2410c", self.on_pause),
            ("⏹️ סיום בלבד", "#be123c", "#9f1239", lambda: self.on_stop(upload=False)),
            ("☁️ סיום והעלאה", "#059669", "#047857", lambda: self.on_stop(upload=True))
        ]

        for i, (text, bg, active_bg, cmd) in enumerate(buttons_def):
            row = i // 4
            col = i % 4
            btn = tk.Button(
                grid_frame,
                text=text,
                font=("Segoe UI", 12, "bold"),
                bg=bg,
                fg="#ffffff",
                activebackground=active_bg,
                activeforeground="#ffffff",
                relief=tk.FLAT,
                cursor="hand2",
                command=cmd
            )
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        for r in range(2):
            grid_frame.grid_rowconfigure(r, weight=1)
        for c in range(4):
            grid_frame.grid_columnconfigure(c, weight=1)

        # Footer Frame
        footer = tk.Frame(self, bg="#111827", height=45)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        server_url_text = f"מחובר לשרת: {config.get('server_url')}"
        footer_lbl = tk.Label(
            footer,
            text=server_url_text,
            font=("Segoe UI", 9),
            fg="#9ca3af",
            bg="#111827"
        )
        footer_lbl.pack(side=tk.LEFT, padx=20, pady=10)

    def check_obs_status_async(self):
        def task():
            ok, msg = self.obs.connect()
            if ok:
                self.status_var.set("🟢 מחובר בהצלחה ל-OBS Studio (מוכן להקלטה)")
            else:
                self.status_var.set("🟡 OBS אינו מחובר - ודא ש-OBS פתוח ו-WebSocket מופעל")
        threading.Thread(target=task, daemon=True).start()

    def on_set_4k(self):
        ok, msg = self.obs.set_4k_canvas()
        if ok:
            messagebox.showinfo("הצלחה", msg)
            self.status_var.set("✅ " + msg)
        else:
            messagebox.showerror("שגיאה", msg)
            self.status_var.set("❌ שגיאה: " + msg)

    def on_action(self, action_name):
        try:
            self.obs.start_record(action_name)
            self.status_var.set(f"🔴 מקליט ב-OBS: [{action_name}] ...")
        except Exception as e:
            messagebox.showerror("שגיאת הקלטה", str(e))
            self.status_var.set(f"❌ שגיאה: {e}")

    def on_pause(self):
        try:
            self.obs.toggle_pause()
            self.status_var.set("⏸️ מצב הקלטה עודכן (הושהה / הומשך)")
        except Exception as e:
            messagebox.showerror("שגיאה", str(e))

    def on_stop(self, upload=True):
        try:
            rec_info = self.obs.stop_record()
            self.status_var.set(f"⏹️ ההקלטה הסתיימה! משך זמן: {rec_info['duration']}")
            if upload:
                self.upload_async(rec_info)
        except Exception as e:
            messagebox.showerror("שגיאת סיום", str(e))

    def upload_async(self, rec_info):
        def task():
            file_path = rec_info.get("file_path")
            server_url = config.get("server_url", "https://liveedits.roi-chocron7.workers.dev").rstrip('/')
            endpoint = f"{server_url}/api/recordings/upload"

            if not file_path or not os.path.exists(file_path):
                self.status_var.set(f"⚠️ הקובץ לא נמצא בנתיב המקומי")
                return

            self.status_var.set(f"🚀 מעלה את {rec_info['file_name']} לשרת הענן...")
            try:
                data = {
                    "id": rec_info["id"],
                    "filename": rec_info["file_name"],
                    "button_used": rec_info["button_used"],
                    "duration": rec_info["duration"],
                    "date_time": rec_info["date_time"]
                }
                with open(file_path, 'rb') as f:
                    files = {'video': (rec_info["file_name"], f, 'video/mp4')}
                    resp = requests.post(endpoint, data=data, files=files, timeout=600)
                if resp.status_code in [200, 201]:
                    self.status_var.set("✅ ההקלטה הועלתה בהצלחה לשרת הענן!")
                else:
                    self.status_var.set(f"⚠️ שרת החזיר {resp.status_code}")
            except Exception as ex:
                self.status_var.set(f"❌ שגיאת העלאה: {ex}")

        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    app = StreamDeckApp()
    app.mainloop()
