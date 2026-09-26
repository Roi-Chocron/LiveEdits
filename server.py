from flask import Flask, jsonify, send_from_directory, request, send_file, redirect, make_response
import os
import sys

# ודא שנתיב הסביבה הווירטואלית (venv) קיים ב-sys.path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_SITE_PACKAGES = [
    os.path.join(_BASE_DIR, 'venv', 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'),
    os.path.join(_BASE_DIR, 'venv', 'lib', 'python3.13', 'site-packages'),
]
for _p in _VENV_SITE_PACKAGES:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import subprocess
import shutil
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime
from werkzeug.utils import secure_filename

# מייבאים את מנהל ה-OBS ואת מסד הנתונים
from obs_controller import obs_controller_instance
import database

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAILS_DIR = os.path.join(BASE_DIR, 'thumbnails')
EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
DRAFTS_DIR = os.path.join(BASE_DIR, 'drafts')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

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

def get_current_user():
    """בודק האם יש משתמש מחובר לפי session_token ב-Cookie או ב-Header"""
    token = request.cookies.get('session_token') or request.headers.get('X-Session-Token')
    if token:
        return database.get_user_by_session(token)
    return None

@app.route('/login')
def login_page():
    """מגיש את דף ההתחברות למערכת"""
    user = get_current_user()
    if user:
        return redirect('/home')
    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """מבצע אימות משתמש ומחזיר Session Token ועוגייה"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = database.authenticate_user(username, password)
    if not user:
        return jsonify({"status": "error", "message": "שם משתמש או סיסמה שגויים"}), 401

    token = database.create_session(user['id'])
    resp = make_response(jsonify({
        "status": "success",
        "user": user,
        "token": token
    }))
    # נגדיר Cookie לתקופה של 7 ימים
    resp.set_cookie('session_token', token, max_age=7*24*3600, path='/', httponly=False)
    return resp

@app.route('/api/auth/logout', methods=['POST', 'GET'])
def api_logout():
    """מתנתק ומבטל את ה-Session"""
    token = request.cookies.get('session_token') or request.headers.get('X-Session-Token')
    if token:
        database.destroy_session(token)
    resp = make_response(redirect('/login'))
    resp.delete_cookie('session_token', path='/')
    return resp

@app.route('/api/auth/me', methods=['GET'])
def api_current_user():
    """מחזיר את פרטי המשתמש המחובר כעת"""
    user = get_current_user()
    if user:
        return jsonify({"status": "success", "user": user})
    return jsonify({"status": "unauthenticated", "user": None}), 401

@app.route('/api/users/editors', methods=['GET'])
def get_editors():
    """מחזיר רשימת עורכים מחוברים מתוך מסד הנתונים"""
    editors = database.get_connected_editors()
    return jsonify(editors)

@app.route('/')
@app.route('/deck')
def stream_deck():
    """מגיש את ה-Stream Deck HTML"""
    user = get_current_user()
    if not user:
        return redirect('/login?next=/deck')
    # אם העורך מנסה לגשת ל-Stream Deck, נציג לו או נעביר ל-home
    return send_from_directory(BASE_DIR, 'stream deck.html')

@app.route('/home')
def home_dashboard():
    """מגיש את ממשק הדשבורד"""
    user = get_current_user()
    if not user:
        return redirect('/login?next=/home')
    return send_from_directory(BASE_DIR, 'home.html')

@app.route('/api/obs-template', methods=['GET'])
@app.route('/live-edits-obs-template.json', methods=['GET'])
def download_obs_template():
    """מוריד את קובץ התבנית של OBS להקלטת גריד 4K"""
    template_path = os.path.join(BASE_DIR, 'live-edits-obs-template.json')
    if os.path.exists(template_path):
        return send_file(
            template_path,
            mimetype='application/json',
            as_attachment=True,
            download_name='live-edits-obs-template.json'
        )
    return jsonify({"status": "error", "message": "קובץ התבנית לא נמצא"}), 404

@app.route('/api/obs/setup-canvas', methods=['POST', 'GET'])
def setup_obs_canvas():
    """מגדיר את רזולוציית OBS ישירות ל-4K גריד (3840x2160) דרך ה-WebSocket"""
    user = get_current_user()
    if user and user.get('role') != 'streamer':
        return jsonify({"status": "error", "message": "הרשאה נדחתה: רק הסטרימר מורשה לשנות הגדרות OBS"}), 403

    success, msg = obs_controller_instance.configure_canvas(3840, 2160)
    if success:
        return jsonify({"status": "success", "message": msg})
    return jsonify({"status": "error", "message": msg}), 500

@app.route('/control', methods=['POST'])
def control_obs():
    """מקבל פקודות מהדפדפן ומעביר ל-OBS Controller (רק לסטרימר)"""
    user = get_current_user()
    if user and user.get('role') != 'streamer':
        return jsonify({"status": "error", "message": "הרשאה נדחתה: רק הסטרימר יכול לשלוט בהקלטות OBS"}), 403

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

@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """מחזיר את כל ההקלטות מתוך מסד הנתונים SQLite"""
    recordings = obs_controller_instance.get_all_recordings()
    return jsonify(recordings)

@app.route('/api/recordings/upload', methods=['POST', 'OPTIONS'])
def upload_recording_from_streamer():
    """מאפשר לאפליקציית הסטרימר להעלות קובץ הקלטה ומטא-דאטה לשרת המרכזי"""
    if request.method == 'OPTIONS':
        return '', 204

    user = get_current_user()
    streamer_id = user['id'] if user else None

    video_file = request.files.get('video')
    if not video_file:
        return jsonify({"status": "error", "message": "לא התקבל קובץ וידאו"}), 400

    filename = request.form.get('filename') or video_file.filename or 'recording.mp4'
    safe_name = secure_filename(filename) or f"rec_{int(time.time())}.mp4"
    target_path = os.path.join(UPLOADS_DIR, safe_name)
    if os.path.exists(target_path):
        time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(safe_name)
        safe_name = f"{base}_{time_tag}{ext}"
        target_path = os.path.join(UPLOADS_DIR, safe_name)

    video_file.save(target_path)

    # יצירת תמונה מקדימה
    thumb_name = f"{os.path.splitext(safe_name)[0]}.jpg"
    thumb_url = obs_controller_instance.generate_thumbnail(target_path, thumb_name)

    record_id = request.form.get('id') or f"remote-{int(time.time())}"
    button_used = request.form.get('button_used') or 'סטרימר מרוחק'
    duration = request.form.get('duration') or '00:00:00'
    date_time = request.form.get('date_time') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record_data = {
        "id": record_id,
        "file_name": safe_name,
        "file_path": target_path,
        "original_path": target_path,
        "button_used": button_used,
        "date_time": date_time,
        "duration": duration,
        "thumbnail": thumb_url,
        "status": "pending",
        "streamer_id": streamer_id
    }

    obs_controller_instance.save_recording_to_json(record_data)

    return jsonify({
        "status": "success",
        "message": "ההקלטה נקלטה בהצלחה במסד הנתונים של השרת",
        "record": record_data
    })

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
    """בודק/מפעיל את openreel-video ומחזיר את כתובת ה-URL לעריכת הסרטון או המשך טיוטה"""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    video_path = data.get('path')
    draft_id = data.get('draftId')
    video_name = data.get('name') or (os.path.basename(video_path) if video_path else 'recording.mp4')

    # אם זו טיוטה קיימת ואין נתיב וידאו מפורש, ננסה להוציא מהטיוטה
    if draft_id and not video_path:
        recordings = obs_controller_instance.get_all_recordings()
        draft_info = next((r for r in recordings if r.get('id') == draft_id), {})
        video_path = draft_info.get('original_path') or draft_info.get('file_path')
        if not video_name or video_name == 'recording.mp4':
            video_name = draft_info.get('file_name') or 'recording.mp4'

    if not draft_id and (not video_path or not os.path.exists(video_path)):
        return jsonify({"status": "error", "message": "קובץ הוידאו לא נמצא"}), 404

    port = start_openreel()
    if not port:
        return jsonify({"status": "error", "message": "לא ניתן להפעיל את openreel-video"}), 500

    base_host = request.host_url.rstrip('/')
    url_params = []

    if draft_id:
        url_params.append(f"draftId={urllib.parse.quote(draft_id)}")
    
    if video_path and os.path.exists(video_path):
        video_stream_url = f"{base_host}/api/video?path={urllib.parse.quote(video_path)}"
        url_params.append(f"videoUrl={urllib.parse.quote(video_stream_url, safe='')}")
        url_params.append(f"videoName={urllib.parse.quote(video_name, safe='')}")

    query_string = "&".join(url_params)
    editor_url = f"http://localhost:{port}/#/editor?{query_string}"

    return jsonify({
        "status": "success",
        "url": editor_url,
        "port": port
    })

@app.route('/api/drafts/save', methods=['POST', 'OPTIONS'])
def save_draft():
    """שומר טיוטה בתהליך עריכה כדי לאפשר המשך עבודה מאיפה שהפסיק"""
    if request.method == 'OPTIONS':
        return '', 204

    if request.is_json:
        data = request.get_json() or {}
    else:
        try:
            raw_text = request.get_data(as_text=True)
            data = json.loads(raw_text) if raw_text else {}
        except Exception:
            data = {}

    project_id = data.get('projectId')
    if not project_id:
        return jsonify({"status": "error", "message": "חסר מזהה פרויקט (projectId)"}), 400

    project_data = data.get('projectData')
    project_name = data.get('projectName') or 'טיוטת עריכה'
    original_video_path = data.get('originalVideoPath') or ''
    original_video_name = data.get('originalVideoName') or (os.path.basename(original_video_path) if original_video_path else project_name)
    duration = data.get('duration') or '00:00:00'
    thumbnail = data.get('thumbnail')

    # חילוץ תמונה מקדימה במידה וחסרה
    if not thumbnail and original_video_path and os.path.exists(original_video_path):
        thumb_name = f"draft_{project_id}.jpg"
        thumbnail = obs_controller_instance.generate_thumbnail(original_video_path, thumb_name)

    # שמירת נתוני הפרויקט לתיקיית drafts
    draft_file_path = os.path.join(DRAFTS_DIR, f"{project_id}.json")
    try:
        with open(draft_file_path, 'w', encoding='utf-8') as f:
            if isinstance(project_data, str):
                f.write(project_data)
            else:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving draft file: {e}")

    # עדכון הלוג recordings_log.json
    draft_record = {
        "id": project_id,
        "file_name": original_video_name,
        "project_name": project_name,
        "file_path": original_video_path,
        "original_path": original_video_path,
        "button_used": "עריכה בתהליך",
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_edited": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration,
        "thumbnail": thumbnail,
        "status": "editing"
    }
    obs_controller_instance.save_draft(draft_record)

    return jsonify({"status": "success", "draftId": project_id})

@app.route('/api/drafts/<draft_id>', methods=['GET'])
def get_draft(draft_id):
    """מחזיר את נתוני הטיוטה עבור עורך הוידאו"""
    draft_file_path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    if not os.path.exists(draft_file_path):
        return jsonify({"status": "error", "message": "הטיוטה לא נמצאה"}), 404

    try:
        with open(draft_file_path, 'r', encoding='utf-8') as f:
            project_obj = json.load(f)

        recordings = obs_controller_instance.get_all_recordings()
        draft_info = next((r for r in recordings if r.get('id') == draft_id), {})
        orig_path = draft_info.get('original_path') or draft_info.get('file_path')

        base_host = request.host_url.rstrip('/')
        video_stream_url = f"{base_host}/api/video?path={urllib.parse.quote(orig_path)}" if orig_path and os.path.exists(orig_path) else None

        return jsonify({
            "status": "success",
            "project": project_obj,
            "original_path": orig_path,
            "file_name": draft_info.get('file_name'),
            "duration": draft_info.get('duration'),
            "video_url": video_stream_url
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/export', methods=['POST', 'OPTIONS'])
def handle_export():
    """מקבל סרטון מיוצא מעורך הוידאו ושומר אותו ישירות בתיקיית exports ללא שאלות"""
    if request.method == 'OPTIONS':
        return '', 204

    video_file = request.files.get('video')
    if not video_file:
        return jsonify({"status": "error", "message": "לא התקבל קובץ וידאו לייצוא"}), 400

    filename = request.form.get('filename') or 'exported_clip.mp4'
    safe_name = secure_filename(filename) or f"export_{int(time.time())}.mp4"
    base, ext = os.path.splitext(safe_name)
    if not ext:
        ext = ".mp4"
        safe_name += ext

    target_path = os.path.join(EXPORTS_DIR, safe_name)
    if os.path.exists(target_path):
        time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{base}_{time_tag}{ext}"
        target_path = os.path.join(EXPORTS_DIR, safe_name)

    video_file.save(target_path)

    # יצירת תמונה מקדימה
    thumb_name = f"{os.path.splitext(safe_name)[0]}.jpg"
    thumb_url = obs_controller_instance.generate_thumbnail(target_path, thumb_name)

    duration = request.form.get('duration') or "00:00:00"
    project_id = request.form.get('projectId')

    export_record = {
        "id": f"export-{int(time.time())}",
        "file_name": safe_name,
        "file_path": target_path,
        "button_used": "ייצוא עורך",
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration,
        "thumbnail": thumb_url,
        "status": "ready"
    }

    obs_controller_instance.save_ready_export(export_record, draft_id_to_clear=project_id)

    return jsonify({
        "status": "success",
        "message": "הסרטון יוצא בהצלחה ונשמר בתיקיית exports",
        "file_name": safe_name,
        "file_path": target_path,
        "thumbnail": thumb_url
    })



if __name__ == '__main__':
    print("🚀 מפעיל את השרת בכתובת http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)