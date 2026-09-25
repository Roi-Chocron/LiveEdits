from flask import Flask, jsonify, send_from_directory, request, send_file
import os
import subprocess
import shutil
import time
import urllib.request
import urllib.parse

# מייבאים את מנהל ה-OBS מהקובץ החדש שיצרנו
from obs_controller import obs_controller_instance

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAILS_DIR = os.path.join(BASE_DIR, 'thumbnails')

@app.after_request
def add_cors_headers(response):
    """מוסיף כותרות CORS ו-CORP כדי לאפשר גישה גם מסביבת OpenReel"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
    return response

def is_port_running(port):
    """בודק אם השרת של OpenReel פעיל בפורט מסוים"""
    for host in ['127.0.0.1', 'localhost']:
        try:
            req = urllib.request.Request(f"http://{host}:{port}/")
            with urllib.request.urlopen(req, timeout=0.6) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            continue
    return False

def get_openreel_port():
    """מוצא את הפורט שבו OpenReel רץ (5174 או 5173)"""
    for p in [5174, 5173]:
        if is_port_running(p):
            return p
    return None

def start_openreel():
    """מפעיל את שרת ה-dev של openreel-video אם הוא עדיין לא רץ"""
    existing_port = get_openreel_port()
    if existing_port:
        return existing_port

    openreel_dir = os.path.join(BASE_DIR, 'openreel-video')
    if not os.path.exists(openreel_dir):
        return None

    pnpm_cmd = shutil.which('pnpm') or '/usr/bin/pnpm'
    try:
        subprocess.Popen(
            [pnpm_cmd, '--filter', '@openreel/web', 'dev', '--port', '5174'],
            cwd=openreel_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        print(f"Error launching openreel: {e}")
        return None

    # ממתינים עד שהשרת יעלה
    for _ in range(14):
        time.sleep(0.5)
        port = get_openreel_port()
        if port:
            return port

    return get_openreel_port()

@app.route('/')
@app.route('/deck')
def stream_deck():
    """מגיש את ה-Stream Deck HTML"""
    return send_from_directory(BASE_DIR, 'stream deck.html')

@app.route('/home')
def home_dashboard():
    """מגיש את ממשק הדשבורד"""
    return send_from_directory(BASE_DIR, 'home.html')

@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """מחזיר את כל ההקלטות מהלוג"""
    recordings = obs_controller_instance.get_all_recordings()
    return jsonify(recordings)

@app.route('/api/thumbnail/<filename>')
def get_thumbnail(filename):
    """מגיש את קובץ התמונה המקדימה"""
    return send_from_directory(THUMBNAILS_DIR, filename)

@app.route('/api/video', methods=['GET', 'OPTIONS'])
def stream_video():
    """מזרים את קובץ הוידאו לצפייה ישירה בפופ-אפ ובעורך"""
    if request.method == 'OPTIONS':
        return '', 204
    video_path = request.args.get('path')
    if video_path and os.path.exists(video_path):
        return send_file(video_path, mimetype='video/mp4')
    return "הקובץ לא נמצא", 404

@app.route('/api/open-editor', methods=['POST', 'OPTIONS'])
def open_editor():
    """בודק/מפעיל את openreel-video ומחזיר את כתובת ה-URL לעריכת הסרטון"""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    video_path = data.get('path')
    video_name = data.get('name') or (os.path.basename(video_path) if video_path else 'recording.mp4')

    if not video_path or not os.path.exists(video_path):
        return jsonify({"status": "error", "message": "קובץ הוידאו לא נמצא"}), 404

    port = start_openreel()
    if not port:
        return jsonify({"status": "error", "message": "לא ניתן להפעיל את openreel-video"}), 500

    base_host = request.host_url.rstrip('/')
    # URL להזרמת הסרטון מהשרת
    video_stream_url = f"{base_host}/api/video?path={urllib.parse.quote(video_path)}"

    # URL לפתיחת OpenReel ישירות בעורך עם הסרטון
    editor_url = f"http://localhost:{port}/#/editor?videoUrl={urllib.parse.quote(video_stream_url, safe='')}&videoName={urllib.parse.quote(video_name, safe='')}"

    return jsonify({
        "status": "success",
        "url": editor_url,
        "port": port
    })

@app.route('/control', methods=['POST'])
def control_obs():
    """מקבל פקודות מהדפדפן ומעביר ל-OBS Controller"""
    data = request.get_json() or {}
    action = data.get('action')
    
    try:
        # התחלת הקלטה
        if action in ['ריאקשן', 'דרמה', 'גיימינג', 'אחר', 'חפיפה']:
            obs_controller_instance.start_recording(action)
            return jsonify({"status": "success", "message": f"ההקלטה התחילה עבור: {action}"})
            
        # השהייה / המשך
        elif action == 'השהיה/המשך':
            obs_controller_instance.toggle_pause()
            return jsonify({"status": "success", "message": "מצב ההקלטה עודכן"})
            
        # סיום הקלטה
        elif action in ['סיום וחזרה', 'סיום בלבד']:
            try:
                # מקבל מה-Controller את הנתיב שבו נשמר הסרטון
                file_path = obs_controller_instance.stop_recording()
                return jsonify({"status": "success", "path": file_path})
            except Exception:
                return jsonify({"status": "success", "message": "ההקלטה כבר הייתה עצורה"})
            
        return jsonify({"status": "error", "message": "פעולה לא מוכרת"}), 400
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("🚀 מפעיל את השרת בכתובת http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)