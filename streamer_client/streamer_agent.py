#!/usr/bin/env python3
"""
LiveEdits Streamer Client Agent
--------------------------------
אפליקציה ייעודית למחשב של הסטרימר.
- מתחברת ישירות ל-OBS Studio המקומי דרך WebSocket (פורט 4455).
- מספקת ממשק Stream Deck מקומי (פורט 5050) לשליטה פשוטה מהירה מהמחשב או מכל סמארטפון/טאבלט.
- מעלה ומסנכרנת אוטומטית את קובץ ההקלטה לשרת הראשי של העורכים ברגע שמסתיימת ההקלטה!
- מאפשרת הגדרת קאנבס 4K מושלם בלחיצת כפתור אחת.
"""

import os
import sys
import time
import socket
import json
import threading
from datetime import datetime

# בדיקה והוספת סביבת פייתון מקומית במידת הצורך
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_SITE = os.path.join(_BASE_DIR, '..', 'venv', 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
if os.path.isdir(_VENV_SITE) and _VENV_SITE not in sys.path:
    sys.path.insert(0, _VENV_SITE)

try:
    from flask import Flask, jsonify, request, render_template_string, send_file, Response
except ImportError:
    print("❌ חסרה ספריית Flask. מנסה להתקין או לטעון...")
    os.system(f"{sys.executable} -m pip install flask requests obsws-python")
    from flask import Flask, jsonify, request, render_template_string, send_file, Response

import requests

CONFIG_PATH = os.path.join(_BASE_DIR, 'config.json')
DEFAULT_CONFIG = {
    "server_url": "https://liveedits.roi-chocron7.workers.dev",
    "streamer_username": "streamer",
    "streamer_password": "streamer123",
    "obs_host": "127.0.0.1",
    "obs_port": 4455,
    "obs_password": "",
    "agent_port": 5050,
    "auto_upload_to_server": True
}

if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    config = DEFAULT_CONFIG
else:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = {**DEFAULT_CONFIG, **json.load(f)}

class LocalOBSController:
    def __init__(self, host='127.0.0.1', port=4455):
        self.host = host
        self.port = port
        self.client = None
        self.current_recording_info = {
            "button_name": None,
            "start_time": None
        }
        self.connect()

    def is_listening(self):
        try:
            with socket.create_connection((self.host, self.port), timeout=0.3):
                return True
        except Exception:
            return False

    def connect(self):
        if self.is_listening():
            try:
                import obsws_python as obs
                pwd = config.get("obs_password", "")
                self.client = obs.ReqClient(host=self.host, port=self.port, password=pwd if pwd else None)
                print("✅ [Streamer Agent] מחובר בהצלחה ל-OBS Studio המקומי!")
                return True
            except Exception as e:
                print(f"⚠️ [Streamer Agent] שגיאה בחיבור ל-OBS: {e}")
                self.client = None
        else:
            print("ℹ️ [Streamer Agent] OBS עדיין אינו פועל (ודא ש-WebSocket מופעל ב-OBS בפורט 4455)")
        return False

    def ensure_connected(self):
        if self.client:
            return True
        return self.connect()

    def configure_4k_grid(self):
        """מגדיר קאנבס 4K ב-OBS"""
        if not self.ensure_connected():
            return False, "אין חיבור ל-OBS. פתח את OBS ובדוק ש-WebSocket מופעל."
        try:
            settings = self.client.get_video_settings()
            fps_num = getattr(settings, 'fps_numerator', 60)
            fps_den = getattr(settings, 'fps_denominator', 1)
            self.client.set_video_settings(fps_num, fps_den, 3840, 2160, 3840, 2160)
            return True, "הקאנבס ב-OBS הוגדר בהצלחה ל-4K גריד (3840x2160)!"
        except Exception as e:
            return False, str(e)

    def start_recording(self, action_name):
        if not self.ensure_connected():
            raise Exception("OBS אינו מחובר. פתח את OBS והפעל את WebSocket.")
        try:
            self.configure_4k_grid()
        except Exception:
            pass
        self.client.start_record()
        self.current_recording_info["button_name"] = action_name
        self.current_recording_info["start_time"] = datetime.now()

    def toggle_pause(self):
        if not self.ensure_connected():
            raise Exception("OBS אינו מחובר")
        self.client.toggle_record_pause()

    def stop_recording(self):
        if not self.ensure_connected():
            raise Exception("OBS אינו מחובר")
        res = self.client.stop_record()
        file_path = getattr(res, 'output_path', '')
        file_name = os.path.basename(file_path) if file_path else 'recording.mp4'

        duration_str = "00:00:00"
        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.current_recording_info["start_time"]:
            dur_sec = int((datetime.now() - self.current_recording_info["start_time"]).total_seconds())
            h = dur_sec // 3600
            m = (dur_sec % 3600) // 60
            s = dur_sec % 60
            duration_str = f"{h:02d}:{m:02d}:{s:02d}"
            formatted_date = self.current_recording_info["start_time"].strftime("%Y-%m-%d %H:%M:%S")

        action_name = self.current_recording_info["button_name"] or "ידני"
        self.current_recording_info["button_name"] = None
        self.current_recording_info["start_time"] = None

        rec_info = {
            "id": f"obs-{int(time.time())}",
            "file_name": file_name,
            "file_path": file_path,
            "button_used": action_name,
            "date_time": formatted_date,
            "duration": duration_str
        }

        # העלאה אוטומטית ברקע לשרת
        if config.get("auto_upload_to_server") and file_path and os.path.exists(file_path):
            t = threading.Thread(target=upload_to_server_async, args=(rec_info,), daemon=True)
            t.start()

        return rec_info

def wait_for_file_complete(file_path, max_wait=20):
    """
    ממתין ש-OBS יסיים לכתוב ולסגור את קובץ ההקלטה בדיסק.
    בודק שהקובץ קיים, גודלו גדול מ-0, ושהגודל התייצב לחלוטין.
    """
    start_time = time.time()
    last_size = -1
    stable_checks = 0
    print(f"⏳ [Auto-Uploader] ממתין ש-OBS יסיים לכתוב את הקובץ {file_path}...")
    while time.time() - start_time < max_wait:
        if os.path.exists(file_path):
            try:
                curr_size = os.path.getsize(file_path)
                if curr_size > 0:
                    if curr_size == last_size:
                        stable_checks += 1
                        if stable_checks >= 2:
                            return True, curr_size
                    else:
                        stable_checks = 0
                        last_size = curr_size
            except Exception:
                pass
        time.sleep(0.5)
    if os.path.exists(file_path):
        sz = os.path.getsize(file_path)
        if sz > 0:
            return True, sz
    return False, 0

# פונקציית העלאה ישירה ל-Google Drive במידה ומחובר, ורישום המטא-דאטה בשרת
def upload_file_to_gdrive(file_path, file_name, access_token):
    """
    מעלה קובץ ישירות ל-Google Drive דרך Resumable Upload API
    תומך בקבצי ענק ללא מגבלות גודל ובאופן אמין ויציב!
    """
    file_size = os.path.getsize(file_path)
    if file_size <= 0:
        raise Exception(f"גודל הקובץ הוא 0 בייט ({file_path}), לא ניתן להעלות")

    print(f"📦 [Google Drive] מתחיל העלאת וידאו {file_name} ({file_size / (1024*1024):.1f} MB)...")

    # 1. יצירת session להעלאה (Resumable Upload)
    metadata = {
        'name': file_name,
        'mimeType': 'video/mp4'
    }
    init_headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': 'video/mp4',
        'X-Upload-Content-Length': str(file_size)
    }
    
    init_res = requests.post(
        'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable',
        headers=init_headers,
        data=json.dumps(metadata),
        timeout=30
    )

    if init_res.status_code != 200:
        raise Exception(f"שגיאה ביצירת העלאה ל-Google Drive ({init_res.status_code}): {init_res.text}")

    upload_url = init_res.headers.get('Location')
    if not upload_url:
        raise Exception("Google Drive לא החזיר כתובת Location להעלאה")

    # 2. הזרמת הקובץ הבינארי ב-chunks של 8MB
    upload_res = None
    chunk_size = 8 * 1024 * 1024
    with open(file_path, 'rb') as f:
        offset = 0
        while offset < file_size:
            chunk = f.read(chunk_size)
            chunk_len = len(chunk)
            content_range = f"bytes {offset}-{offset + chunk_len - 1}/{file_size}"
            
            chunk_headers = {
                'Content-Length': str(chunk_len),
                'Content-Range': content_range
            }

            upload_res = requests.put(upload_url, headers=chunk_headers, data=chunk, timeout=300)
            offset += chunk_len
            percent = int((offset / file_size) * 100)
            print(f"⏳ [Google Drive] קצב העלאה: {percent}% ({offset / (1024*1024):.1f}MB)")

    if not upload_res or upload_res.status_code not in [200, 201]:
        err_msg = upload_res.text if upload_res else "No response"
        status_c = upload_res.status_code if upload_res else "None"
        raise Exception(f"שגיאה בהשלמת העלאה ל-Google Drive ({status_c}): {err_msg}")

    file_data = upload_res.json()
    file_id = file_data.get('id')
    print(f"🎉 [Google Drive] הסרטון הועלה בהצלחה! File ID: {file_id}")

    # 3. הגדרת הרשאת קריאה ציבורית לקובץ כדי שהעורכים יוכלו לצפות בו מיד
    try:
        perm_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
        perm_data = {'role': 'reader', 'type': 'anyone'}
        requests.post(perm_url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json=perm_data, timeout=15)
    except Exception as e:
        print(f"⚠️ [Google Drive] לא ניתן להגדיר הרשאת שיתוף ציבורית: {e}")

    return {
        "gdrive_id": file_id,
        "gdrive_view_url": f"https://drive.google.com/file/d/{file_id}/preview",
        "gdrive_download_url": f"https://drive.google.com/uc?export=download&id={file_id}",
        "thumbnail": f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
    }

# פונקציית העלאת ההקלטה לשרת / Google Drive
def upload_to_server_async(rec_info):
    server_url = config.get("server_url", "https://liveedits.roi-chocron7.workers.dev").rstrip('/')
    upload_endpoint = f"{server_url}/api/recordings/upload"
    token_endpoint = f"{server_url}/api/gdrive/token"
    file_path = rec_info.get("file_path")
    file_name = rec_info.get("file_name")
    
    print(f"🚀 [Auto-Uploader] מעבד את ההקלטה {file_name}...")

    # המתנה לסיום כתיבת הקובץ על ידי OBS
    ready, file_size = wait_for_file_complete(file_path)
    if not ready or file_size == 0:
        print(f"⚠️ [Auto-Uploader] הקובץ {file_path} לא נמצא או ריק!")
        return

    gdrive_meta = {}
    try:
        # בדיקה האם יש טוקן פעיל של Google Drive בשרת
        token_resp = requests.get(token_endpoint, timeout=10)
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            access_token = token_data.get("token")
            if access_token:
                print("☁️ [Auto-Uploader] נמצא חיבור ל-Google Drive, מעלה ישירות לענן...")
                gdrive_meta = upload_file_to_gdrive(file_path, file_name, access_token)
                print("✅ [Auto-Uploader] ההקלטה נשמרה ב-Google Drive!")
    except Exception as gerr:
        print(f"⚠️ [Auto-Uploader] העלאה ל-Google Drive נכשלה (ממשיך בשמירת מטא-דאטה): {gerr}")

    # רישום המטא-דאטה של ההקלטה בשרת Cloudflare KV
    try:
        data = {
            "id": rec_info.get("id"),
            "filename": file_name,
            "file_path": file_path,
            "original_path": file_path,
            "button_used": rec_info.get("button_used"),
            "duration": rec_info.get("duration"),
            "date_time": rec_info.get("date_time"),
            "gdrive_id": gdrive_meta.get("gdrive_id", ""),
            "gdrive_view_url": gdrive_meta.get("gdrive_view_url", ""),
            "gdrive_download_url": gdrive_meta.get("gdrive_download_url", ""),
            "thumbnail": gdrive_meta.get("thumbnail", "")
        }
        
        response = requests.post(upload_endpoint, json=data, timeout=30)
        if response.status_code in [200, 201]:
            print(f"✅ [Auto-Uploader] ההקלטה {file_name} סונכרנה בהצלחה לדשבורד העורכים!")
        else:
            print(f"⚠️ [Auto-Uploader] השרת החזיר תשובה {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ [Auto-Uploader] שגיאה בסנכרון ההקלטה לשרת: {e}")

obs_ctrl = LocalOBSController(host=config["obs_host"], port=config["obs_port"])
app = Flask(__name__)

STREAM_DECK_HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LiveEdits Streamer Client</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Assistant', sans-serif; background-color: #0b0f19; color: #f8fafc; }</style>
</head>
<body class="min-h-screen flex flex-col justify-between p-6">
    <header class="max-w-4xl mx-auto w-full flex justify-between items-center bg-slate-900/90 backdrop-blur p-4 rounded-2xl border border-indigo-900/40 shadow-xl">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white text-lg shadow">
                <i class="fa-solid fa-satellite-dish"></i>
            </div>
            <div>
                <h1 class="font-bold text-base text-white">LiveEdits Streamer Agent</h1>
                <p class="text-xs text-indigo-300">חיבור ישיר ל-OBS Studio & העלאה אוטומטית לענן</p>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="setupCanvas()" class="bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow">
                <i class="fa-solid fa-sliders"></i> 4K Grid Canvas
            </button>
            <a href="{{ server_url }}/home" target="_blank" class="bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow">
                <i class="fa-solid fa-cloud"></i> פתח שרת ענן
            </a>
        </div>
    </header>

    <main class="max-w-4xl mx-auto w-full my-8 flex flex-col items-center">
        <!-- Status Box -->
        <div id="statusMsg" class="mb-6 text-sm font-semibold text-sky-400 h-6 text-center">מוכן לפעולה מול OBS</div>

        <!-- Buttons Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full">
            <button onclick="sendAction('ריאקשן')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-indigo-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-face-laugh-squint text-indigo-400 text-3xl"></i>
                <span>ריאקשן</span>
            </button>
            <button onclick="sendAction('דרמה')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-indigo-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-masks-theater text-amber-400 text-3xl"></i>
                <span>דרמה</span>
            </button>
            <button onclick="sendAction('גיימינג')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-indigo-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-gamepad text-emerald-400 text-3xl"></i>
                <span>גיימינג</span>
            </button>
            <button onclick="sendAction('חפיפה')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-indigo-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-layer-group text-purple-400 text-3xl"></i>
                <span>חפיפה</span>
            </button>

            <button onclick="sendAction('אחר')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-indigo-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-ellipsis text-slate-400 text-3xl"></i>
                <span>אחר</span>
            </button>
            <button onclick="sendAction('השהיה/המשך')" class="bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-amber-500 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-pause text-amber-400 text-3xl"></i>
                <span>השהיה / המשך</span>
            </button>
            <button onclick="sendAction('סיום בלבד')" class="bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800 text-rose-200 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-stop text-rose-400 text-3xl"></i>
                <span>סיום בלבד</span>
            </button>
            <button onclick="sendAction('סיום וחזרה')" class="bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800 text-emerald-200 rounded-2xl h-36 font-bold text-xl transition hover:scale-105 shadow-lg flex flex-col items-center justify-center gap-2 cursor-pointer">
                <i class="fa-solid fa-cloud-arrow-up text-emerald-400 text-3xl"></i>
                <span>סיום והעלאה</span>
            </button>
        </div>

        <div class="mt-8 bg-slate-900/60 border border-slate-800 p-4 rounded-xl text-center text-xs text-slate-400 w-full max-w-xl">
            💡 <strong>העלאה אוטומטית פעילה:</strong> בעת לחיצה על "סיום", הקובץ נשמר מקומית ב-OBS ומועבר מיד ברקע לשרת הענן לעורכים.
        </div>
    </main>

    <footer class="max-w-4xl mx-auto w-full text-center text-xs text-slate-500 py-3 border-t border-slate-800">
        LiveEdits Streamer Client • מחובר לשרת: <span class="text-indigo-400 font-mono">{{ server_url }}</span>
    </footer>

    <script>
        const statusDiv = document.getElementById('statusMsg');

        async function sendAction(action) {
            statusDiv.textContent = `מבצע: ${action}...`;
            try {
                const res = await fetch('/api/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                const data = await res.json();
                if (res.ok) {
                    statusDiv.textContent = `✅ ${data.message || 'בוצע בהצלחה'}`;
                } else {
                    statusDiv.textContent = `❌ ${data.message}`;
                }
            } catch (err) {
                statusDiv.textContent = '❌ שגיאת תקשורת עם ה-Streamer Agent המקומי';
            }
        }

        async function setupCanvas() {
            statusDiv.textContent = 'מגדיר רזולוציית 4K ב-OBS...';
            try {
                const res = await fetch('/api/obs/canvas-4k', { method: 'POST' });
                const data = await res.json();
                alert(data.message);
                statusDiv.textContent = `✅ ${data.message}`;
            } catch (err) {
                alert('שגיאה: ' + err.message);
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(STREAM_DECK_HTML, server_url=config.get("server_url", "https://liveedits.roi-chocron7.workers.dev"))

@app.route('/api/obs/canvas-4k', methods=['POST', 'GET'])
def set_canvas():
    success, msg = obs_ctrl.configure_4k_grid()
    return jsonify({"status": "success" if success else "error", "message": msg})

@app.route('/api/control', methods=['POST'])
def control():
    data = request.get_json() or {}
    action = data.get('action')

    try:
        if action in ['ריאקשן', 'דרמה', 'גיימינג', 'אחר', 'חפיפה']:
            obs_ctrl.start_recording(action)
            return jsonify({"status": "success", "message": f"הקלטה פעילה ב-OBS: {action}"})

        elif action == 'השהיה/המשך':
            obs_ctrl.toggle_pause()
            return jsonify({"status": "success", "message": "מצב ההקלטה עודכן"})

        elif action in ['סיום וחזרה', 'סיום בלבד']:
            rec_info = obs_ctrl.stop_recording()
            return jsonify({
                "status": "success",
                "message": f"ההקלטה הסתיימה ({rec_info.get('duration')}) ונשלחה להעלאה לשרת!",
                "recording": rec_info
            })

        return jsonify({"status": "error", "message": "פעולה לא ידועה"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.route("/api/video", methods=["GET", "OPTIONS"])
def stream_video():
    if request.method == "OPTIONS":
        return "", 204
    video_path = request.args.get("path")
    if not video_path:
        return "Missing video path", 400

    candidates = [
        video_path,
        os.path.join(os.path.expanduser("~"), video_path),
        os.path.join(os.path.expanduser("~"), "Videos", video_path),
        os.path.join(os.path.expanduser("~"), "וידאו", video_path),
        os.path.join(_BASE_DIR, video_path)
    ]
    target = None
    for cand in candidates:
        if os.path.isfile(cand):
            target = cand
            break

    if target:
        return send_file(target, mimetype="video/mp4", as_attachment=False)
    return f"File not found: {video_path}", 404

if __name__ == '__main__':
    port = config.get("agent_port", 5050)
    print(f"🎮 מפעיל את LiveEdits Streamer Client בכתובת http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

