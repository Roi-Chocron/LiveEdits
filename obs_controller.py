import obsws_python as obs
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

# יצירת תיקיית thumbnails במידה ולא קיימת
os.makedirs(THUMBNAILS_DIR, exist_ok=True)

class OBSManager:
    def __init__(self):
        """מאתחל את החיבור ל-OBS ואת משתני המעקב"""
        self.current_recording_info = {
            "button_name": None,
            "start_time": None
        }
        
        try:
            self.client = obs.ReqClient(host='localhost', port=4455)
            print("✅ התחברות ל-OBS עברה בהצלחה")
        except Exception as e:
            print(f"❌ שגיאה בחיבור ל-OBS: {e}")
            self.client = None

    def start_recording(self, action_name):
        """מתחיל הקלטה ושומר את נתוני ההתחלה"""
        if not self.client:
            raise Exception("אין חיבור פעיל ל-OBS")
        
        try:
            self.client.start_record()
        except Exception:
            pass # אם ההקלטה כבר רצה נתעלם מהשגיאה
            
        self.current_recording_info["button_name"] = action_name
        self.current_recording_info["start_time"] = datetime.now()

    def toggle_pause(self):
        """משהה או ממשיך הקלטה קיימת"""
        if not self.client:
            raise Exception("אין חיבור פעיל ל-OBS")
        self.client.toggle_record_pause()

    def stop_recording(self):
        """עוצר את ההקלטה, שומר תמונה מקדימה ומעדכן את קובץ ה-JSON"""
        if not self.client:
            raise Exception("אין חיבור פעיל ל-OBS")
            
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
        record_data = {
            "file_name": file_name,
            "file_path": file_path,
            "button_used": self.current_recording_info["button_name"] or "ידני / לא ידוע",
            "date_time": formatted_date,
            "duration": duration_str,
            "thumbnail": thumb_url
        }
        
        # שמירה לקובץ ולאיפוס משתנים
        self.save_recording_to_json(record_data)
        self.current_recording_info["button_name"] = None
        self.current_recording_info["start_time"] = None
        
        return file_path

    def generate_thumbnail(self, video_path, thumb_name):
        """מחלץ פריים ראשון מהוידאו ויוצר תמונה"""
        if not OPENCV_AVAILABLE or not os.path.exists(video_path):
            return None
            
        # השהייה קלה כדי ש-OBS יסיים לסגור ולשמור את קובץ הוידאו
        time.sleep(1.5)
        
        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_name)
        try:
            cap = cv2.VideoCapture(video_path)
            success, frame = cap.read()
            if success:
                cv2.imwrite(thumb_path, frame)
                cap.release()
                return f"/api/thumbnail/{thumb_name}"
            cap.release()
        except Exception as ex:
            print(f"שגיאה ביצירת תמונה מקדימה: {ex}")
        return None

    def save_recording_to_json(self, record_data):
        """שומר את נתוני ההקלטה בקובץ ה-JSON"""
        data_list = []
        if os.path.exists(JSON_LOG_FILE):
            try:
                with open(JSON_LOG_FILE, 'r', encoding='utf-8') as f:
                    data_list = json.load(f)
            except Exception:
                pass
                
        data_list.append(record_data)
        
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