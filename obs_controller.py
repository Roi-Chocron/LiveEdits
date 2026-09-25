import socket
import os
import time
from datetime import datetime
import json

# ננסה לייבא את OpenCV עבור התמונות המקדימות
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# הגדרת נתיבי קבצים
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_LOG_FILE = os.path.join(BASE_DIR, 'recordings_log.json')
THUMBNAILS_DIR = os.path.join(BASE_DIR, 'thumbnails')
EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
DRAFTS_DIR = os.path.join(BASE_DIR, 'drafts')

# יצירת התיקיות במידה ואינן קיימות
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(DRAFTS_DIR, exist_ok=True)

def is_obs_listening(host='127.0.0.1', port=4455, timeout=0.15):
    """בודק האם פורט ה-WebSocket של OBS פתוח לחיבור מבלי לעורר חריגות"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

class OBSManager:
    def __init__(self):
        """מאתחל את מנהל ה-OBS בצורה שקטה מבלי לקרוס כשהתוכנה סגורה"""
        self.current_recording_info = {
            "button_name": None,
            "start_time": None
        }
        self.client = None
        
        # חיבור ראשוני רק אם OBS פועל ברקע
        if is_obs_listening():
            try:
                import obsws_python as obs
                self.client = obs.ReqClient(host='localhost', port=4455)
                print("✅ התחברות ל-OBS עברה בהצלחה")
            except Exception as e:
                print(f"❌ שגיאה בחיבור ל-OBS: {e}")
                self.client = None
        else:
            print("ℹ️ OBS אינו פועל כרגע (ניתן להמשיך להשתמש בעורך ולצפות בהקלטות)")

    def ensure_client(self):
        """מוודא חיבור פעיל ל-OBS ומנסה להתחבר מחדש במידת הצורך"""
        if self.client:
            return True
        if is_obs_listening():
            try:
                import obsws_python as obs
                self.client = obs.ReqClient(host='localhost', port=4455)
                print("✅ התחברות מחודשת ל-OBS עברה בהצלחה")
                return True
            except Exception as e:
                print(f"❌ ניסיון התחברות ל-OBS נכשל: {e}")
                self.client = None
                return False
        return False

    def start_recording(self, action_name):
        """מתחיל הקלטה ושומר את נתוני ההתחלה"""
        if not self.ensure_client():
            raise Exception("אין חיבור פעיל ל-OBS. ודא שתוכנת OBS פועלת ושה-WebSocket מופעל.")
        
        try:
            self.client.start_record()
        except Exception:
            pass # אם ההקלטה כבר רצה נתעלם מהשגיאה
            
        self.current_recording_info["button_name"] = action_name
        self.current_recording_info["start_time"] = datetime.now()

    def toggle_pause(self):
        """משהה או ממשיך הקלטה קיימת"""
        if not self.ensure_client():
            raise Exception("אין חיבור פעיל ל-OBS. ודא שתוכנת OBS פועלת.")
        self.client.toggle_record_pause()

    def stop_recording(self):
        """עוצר את ההקלטה, שומר תמונה מקדימה ומעדכן את קובץ ה-JSON"""
        if not self.ensure_client():
            raise Exception("אין חיבור פעיל ל-OBS. ודא שתוכנת OBS פועלת.")
            
        res = self.client.stop_record()
        file_path = getattr(res, 'output_path', 'לא ידוע')
        file_name = os.path.basename(file_path) if file_path != 'לא ידוע' else 'לא ידוע'
        
        duration_str = "00:00:00"
        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # חישוב אורך ההקלטה
        if self.current_recording_info["start_time"]:
            end_time = datetime.now()
            duration_seconds = int((end_time - self.current_recording_info["start_time"]).total_seconds())
            
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            formatted_date = self.current_recording_info["start_time"].strftime("%Y-%m-%d %H:%M:%S")

        # יצירת תמונה מקדימה
        thumb_filename = f"{os.path.splitext(file_name)[0]}.jpg" if file_name != 'לא ידוע' else None
        thumb_url = self.generate_thumbnail(file_path, thumb_filename) if thumb_filename else None

        # ארגון הנתונים
        record_id = f"obs-{int(time.time())}"
        record_data = {
            "id": record_id,
            "file_name": file_name,
            "file_path": file_path,
            "button_used": self.current_recording_info["button_name"] or "ידני / לא ידוע",
            "date_time": formatted_date,
            "duration": duration_str,
            "thumbnail": thumb_url,
            "status": "pending"
        }
        
        # שמירה לקובץ ולאיפוס משתנים
        self.save_recording_to_json(record_data)
        self.current_recording_info["button_name"] = None
        self.current_recording_info["start_time"] = None
        
        return file_path

    def generate_thumbnail(self, video_path, thumb_name):
        """מחלץ פריים מהוידאו ויוצר תמונה מקדימה באיכות טובה"""
        if not OPENCV_AVAILABLE or not os.path.exists(video_path):
            return None
            
        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            # ננסה לחלץ פריים לאחר חצי שנייה כדי להימנע מפריים שחור בהתחלה
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 0.5))
            success, frame = cap.read()
            if not success or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
                
            if success and frame is not None:
                cv2.imwrite(thumb_path, frame)
                cap.release()
                return f"/api/thumbnail/{thumb_name}"
            cap.release()
        except Exception as ex:
            print(f"שגיאה ביצירת תמונה מקדימה: {ex}")
        return None

    def save_recording_to_json(self, record_data):
        """שומר את נתוני ההקלטה בקובץ ה-JSON"""
        data_list = self.get_all_recordings()
        data_list.append(record_data)
        with open(JSON_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)

    def save_draft(self, draft_data):
        """שומר או מעדכן קליפ בתהליך עריכה בקובץ ה-JSON"""
        data_list = self.get_all_recordings()
        draft_id = draft_data.get('id')
        found = False
        for i, item in enumerate(data_list):
            if item.get('id') == draft_id:
                data_list[i] = {**item, **draft_data, "status": "editing"}
                found = True
                break
        if not found:
            data_list.append({**draft_data, "status": "editing"})

        with open(JSON_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)

    def save_ready_export(self, export_data, draft_id_to_clear=None):
        """שומר קליפ מוכן בקובץ ה-JSON ומנקה טיוטה אם קיימת"""
        data_list = self.get_all_recordings()
        
        # אם יש טיוטה שקושרה לייצוא הזה, נמחק אותה או נעדכן אותה
        if draft_id_to_clear:
            data_list = [item for item in data_list if item.get('id') != draft_id_to_clear]
            
        data_list.append({**export_data, "status": "ready"})
        
        with open(JSON_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)

    def delete_draft_by_id(self, draft_id):
        """מוחק טיוטת עריכה מקובץ ה-JSON"""
        data_list = self.get_all_recordings()
        data_list = [item for item in data_list if item.get('id') != draft_id]
        with open(JSON_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)

    def get_all_recordings(self):
        """שולף את כל ההקלטות מקובץ ה-JSON"""
        if os.path.exists(JSON_LOG_FILE):
            try:
                with open(JSON_LOG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return []

# יצירת מופע גלובלי של מנהל ה-OBS שנוכל לייבא בשרת
obs_controller_instance = OBSManager()