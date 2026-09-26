import sqlite3
import os
import json
import hashlib
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'liveedits.db')
LEGACY_JSON_PATH = os.path.join(BASE_DIR, 'recordings_log.json')

def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = "LiveEditsSecureSalt2026"
    return hashlib.sha256(f"{salt}_{password}".encode('utf-8')).hexdigest()

def get_db_connection():
    """Returns a SQLite connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes tables and migrates existing JSON logs into SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # טבלת משתמשים עם תפקידים: streamer / editor
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('streamer', 'editor')),
        avatar TEXT,
        created_at TEXT NOT NULL
    )
    ''')

    # טבלת Sessions למשתמשים מחוברים
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    ''')

    # טבלת הקלטות, טיוטות וקליפים מוכנים
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recordings (
        id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL,
        project_name TEXT,
        file_path TEXT NOT NULL,
        original_path TEXT,
        button_used TEXT,
        date_time TEXT NOT NULL,
        last_edited TEXT,
        duration TEXT DEFAULT '00:00:00',
        thumbnail TEXT,
        status TEXT NOT NULL CHECK(status IN ('pending', 'editing', 'ready')),
        streamer_id INTEGER,
        assigned_editor_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (streamer_id) REFERENCES users (id),
        FOREIGN KEY (assigned_editor_id) REFERENCES users (id)
    )
    ''')

    # יצירת משתמשי ברירת מחדל במידה ולא קיימים
    default_users = [
        ("streamer", hash_password("streamer123"), "עודד (סטרימר)", "streamer", None),
        ("editor1", hash_password("editor123"), "דניאל (עורך)", "editor", None),
        ("editor2", hash_password("editor123"), "אבני (עורך)", "editor", None),
    ]

    for username, pwd_hash, display_name, role, avatar in default_users:
        cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, display_name, role, avatar, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, pwd_hash, display_name, role, avatar, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()

    # הגירת נתונים קיימים מ-recordings_log.json למסד הנתונים
    if os.path.exists(LEGACY_JSON_PATH):
        try:
            with open(LEGACY_JSON_PATH, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                if isinstance(logs, list):
                    for item in logs:
                        rec_id = str(item.get('id') or f"rec-{int(time.time())}-{hash(item.get('file_name', ''))}")
                        status = item.get('status')
                        if not status:
                            status = 'ready' if item.get('is_ready') else 'pending'
                        
                        cursor.execute('''
                        INSERT OR IGNORE INTO recordings (
                            id, file_name, project_name, file_path, original_path,
                            button_used, date_time, last_edited, duration,
                            thumbnail, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            rec_id,
                            item.get('file_name') or 'clip.mp4',
                            item.get('project_name'),
                            item.get('file_path') or '',
                            item.get('original_path'),
                            item.get('button_used') or 'ידני',
                            item.get('date_time') or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            item.get('last_edited'),
                            item.get('duration') or '00:00:00',
                            item.get('thumbnail'),
                            status,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ))
                    conn.commit()
        except Exception as e:
            print(f"⚠️ Error migrating JSON log to SQLite: {e}")

    conn.close()

# ----------------- User & Authentication Functions -----------------

def authenticate_user(username, password):
    """Verifies username and password, returns user dict or None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    cursor.execute('''
    SELECT id, username, display_name, role, avatar FROM users
    WHERE username = ? AND password_hash = ?
    ''', (username, pwd_hash))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_session(user_id: int, duration_seconds: int = 7 * 24 * 3600) -> str:
    """Generates and stores a session token."""
    token = hashlib.sha256(f"{user_id}_{time.time()}_{os.urandom(16)}".encode('utf-8')).hexdigest()
    expires_at = int(time.time()) + duration_seconds
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO sessions (token, user_id, created_at, expires_at)
    VALUES (?, ?, ?, ?)
    ''', (token, user_id, now_str, expires_at))
    conn.commit()
    conn.close()
    return token

def get_user_by_session(token: str):
    """Retrieves user info from active session token."""
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    now_ts = int(time.time())
    cursor.execute('''
    SELECT u.id, u.username, u.display_name, u.role, u.avatar
    FROM sessions s
    JOIN users u ON s.user_id = u.id
    WHERE s.token = ? AND s.expires_at > ?
    ''', (token, now_ts))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def destroy_session(token: str):
    """Deletes a session token on logout."""
    if not token:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
    conn.commit()
    conn.close()

def get_connected_editors():
    """Returns list of active editors for display in dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, username, display_name, role, avatar FROM users
    WHERE role = 'editor'
    ORDER BY id ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- Recordings & Clips Database Functions -----------------

def db_add_recording(record_data: dict):
    """Adds a newly recorded OBS clip to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    rec_id = record_data.get('id') or f"obs-{int(time.time())}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
    INSERT OR REPLACE INTO recordings (
        id, file_name, project_name, file_path, original_path,
        button_used, date_time, last_edited, duration,
        thumbnail, status, streamer_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        rec_id,
        record_data.get('file_name'),
        record_data.get('project_name'),
        record_data.get('file_path'),
        record_data.get('original_path') or record_data.get('file_path'),
        record_data.get('button_used') or 'ידני',
        record_data.get('date_time') or now_str,
        record_data.get('last_edited'),
        record_data.get('duration') or '00:00:00',
        record_data.get('thumbnail'),
        record_data.get('status') or 'pending',
        record_data.get('streamer_id'),
        now_str
    ))
    conn.commit()
    conn.close()

def db_save_draft(draft_data: dict):
    """Saves or updates an in-progress editing draft."""
    conn = get_db_connection()
    cursor = conn.cursor()
    draft_id = draft_data.get('id')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
    INSERT OR REPLACE INTO recordings (
        id, file_name, project_name, file_path, original_path,
        button_used, date_time, last_edited, duration,
        thumbnail, status, streamer_id, assigned_editor_id, created_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'editing', ?, ?,
        COALESCE((SELECT created_at FROM recordings WHERE id = ?), ?)
    )
    ''', (
        draft_id,
        draft_data.get('file_name'),
        draft_data.get('project_name') or draft_data.get('file_name'),
        draft_data.get('file_path') or '',
        draft_data.get('original_path') or draft_data.get('file_path') or '',
        draft_data.get('button_used') or 'עריכה בתהליך',
        draft_data.get('date_time') or now_str,
        draft_data.get('last_edited') or now_str,
        draft_data.get('duration') or '00:00:00',
        draft_data.get('thumbnail'),
        draft_data.get('streamer_id'),
        draft_data.get('assigned_editor_id'),
        draft_id,
        now_str
    ))
    conn.commit()
    conn.close()

def db_save_ready_export(export_data: dict, draft_id_to_clear=None):
    """Saves a finished exported clip and removes/clears the associated draft."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if draft_id_to_clear:
        cursor.execute('DELETE FROM recordings WHERE id = ?', (draft_id_to_clear,))

    rec_id = export_data.get('id') or f"export-{int(time.time())}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
    INSERT OR REPLACE INTO recordings (
        id, file_name, project_name, file_path, original_path,
        button_used, date_time, last_edited, duration,
        thumbnail, status, streamer_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?)
    ''', (
        rec_id,
        export_data.get('file_name'),
        export_data.get('project_name'),
        export_data.get('file_path'),
        export_data.get('original_path') or export_data.get('file_path'),
        export_data.get('button_used') or 'ייצוא עורך',
        export_data.get('date_time') or now_str,
        export_data.get('last_edited'),
        export_data.get('duration') or '00:00:00',
        export_data.get('thumbnail'),
        export_data.get('streamer_id'),
        now_str
    ))
    conn.commit()
    conn.close()

def db_delete_recording(recording_id: str):
    """Deletes a recording or draft by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM recordings WHERE id = ?', (recording_id,))
    conn.commit()
    conn.close()

def db_get_all_recordings():
    """Retrieves all clips/recordings/drafts ordered by latest date."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT r.*, u.display_name as streamer_name
    FROM recordings r
    LEFT JOIN users u ON r.streamer_id = u.id
    ORDER BY r.rowid DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize tables when module is imported
init_db()
