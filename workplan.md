# LiveEdits - תוכנית עבודה לסוכני פיתוח (Antigravity Agents)

**מטרת המערכת:** פלטפורמת עריכת וידאו מבוססת דפדפן (מבוססת קוד פתוח OpenReel) המאפשרת לסטרימר להקליט קליפים דרך ממשק דמוי Stream Deck, ולהעבירם אוטומטית ובזמן אמת לעורכים מרוחקים, כולל אפשרות ייצוא והעלאה ישירה ליוטיוב.

---

## 🔗 חוזים משותפים (Shared Contracts - חובה על כל הסוכנים)

כדי ששלושת הסוכנים יעבדו במקביל ללא התנגשויות תחת פרויקט LiveEdits, להלן המוסכמות המשותפות:

*   **כתובת השרת המרכזי:** `http://localhost:4000` (או הכתובת בענן).
*   **אירועי Socket.io:**
    *   `deck-trigger`: שליחת פקודת התחלה/עצירה מהדפדפן לשרת (Payload: `{ action: 'start'|'stop', category: string, quality: string }`).
    *   `obs-command`: השרת שולח ל-Streamer Agent פקודה ל-OBS (Payload: `{ action: 'start'|'stop', metadata: object }`).
    *   `clip-ready`: השרת מודיע לעורכים שווידאו מוכן (Payload: `{ id: string, url: string, category: string, duration: number }`).
*   **API Endpoints (Server):**
    *   `POST /api/upload` - קבלת `multipart/form-data` עם שדה `video`.
    *   `POST /api/youtube/publish` - קבלת נתוני פרסום (JSON) ל-YouTube.

---

## 🤖 Agent 1: משימות השרת (Server Cloud Agent)
**תיקיית עבודה:** `/live-edits/server`
**טכנולוגיות:** Node.js, Express, Socket.io, Multer, Googleapis (YouTube v3).

### משימות תשתית וחיבורים:
- [ ] אתחול פרויקט Node.js והתקנת תלויות (express, cors, socket.io, multer, googleapis, dotenv).
- [ ] יצירת קובץ `server.js` והקמת שרת Express בסיסי.
- [ ] שילוב Socket.io בשרת והגדרת CORS לקבלת בקשות מכל מקור.
- [ ] הגדרת הגשת קבצים סטטיים (Static Hosting) מתיקיית `uploads/`.

### ניהול Socket.io (Realtime Events):
- [ ] הגדרת מאזין לאירוע `deck-trigger` שמגיע מהקליינט.
- [ ] ניתוב פקודות: בעת קבלת `deck-trigger`, שליחת `obs-command` בחזרה ל-Streamer Agent הרלוונטי.
- [ ] הגדרת פונקציה לפליטת אירוע `clip-ready` לכלל משתמשי הקליינט (העורכים).

### ניהול קבצים (Upload API):
- [ ] יצירת `middleware/storage.js` באמצעות Multer: שמירת קבצים בתיקיית `uploads/` ושמירה על סיומת הקובץ המקורית.
- [ ] יצירת הראוטר `routes/upload.js`: קבלת הקובץ, שמירתו, והפעלת פליטת ה-Socket `clip-ready` עם כתובת ה-URL הסטטית שלו.

### אינטגרציית YouTube:
- [ ] יצירת `services/youtube-uploader.js`: הגדרת `OAuth2Client` ושימוש ב-Token קיים מקובץ `.env`.
- [ ] כתיבת הפונקציה `uploadToYouTube` שמזרימה קובץ מקומי ל-YouTube Data API v3.
- [ ] יצירת הראוטר `routes/youtube.js` שחושף את פונקציית ההעלאה ל-Frontend.

---

## 🤖 Agent 2: משימות סוכן הסטרימר (Streamer Local Agent)
**תיקיית עבודה:** `/live-edits/streamer-agent`
**טכנולוגיות:** Node.js, obs-websocket-js, fluent-ffmpeg, axios, socket.io-client.

### משימות תשתית ותקשורת:
- [ ] אתחול הפרויקט והתקנת תלויות (obs-websocket-js, fluent-ffmpeg, axios, socket.io-client, dotenv).
- [ ] יצירת `config.js` לטעינת הגדרות (.env: OBS port, password, Server URL).
- [ ] הקמת החיבור ל-OBS WebSocket באמצעות `obs-websocket-js`.
- [ ] הקמת חיבור לשרת המרכזי באמצעות `socket.io-client` והאזנה ל-`obs-command`.

### שליטה ובקרה ב-OBS:
- [ ] כתיבת פונקציה `triggerObsRecord` שמקבלת פקודת התחלה/עצירה ושולחת ל-OBS.
- [ ] רישום מאזין לאירוע `RecordStateChanged` מ-OBS לזיהוי סיום הקלטה ושליפת נתיב הקובץ (`outputPath`).

### דחיסה והעלאה:
- [ ] יצירת `compressor.js`: שימוש ב-FFmpeg (דרך `fluent-ffmpeg`) לפרופילי איכות (Ultrafast 480p, Veryfast 720p, Bypass/Original).
- [ ] יצירת `uploader.js`: קריאת הקובץ (הדחוס או המקורי) ושליחתו כ-`FormData` ל-`POST /api/upload` בשרת המרכזי באמצעות Axios.
- [ ] חיבור הלוגיקה: עם סיום ההקלטה ב-OBS -> דחיסה בהתאם לבקשה -> העלאה לשרת.

---

## 🤖 Agent 3: משימות הלקוח (Frontend Client Agent)
**תיקיית עבודה:** `/live-edits/client`
**טכנולוגיות:** React / Next.js, Tailwind CSS, Socket.io-client, OpenReel.

### תשתית וסרוויסים:
- [ ] הקמת סביבת הפרויקט והתקנת תלויות (socket.io-client, axios, lucide-react).
- [ ] יצירת `services/socket.js`: אתחול החיבור לשרת, וחשיפת פונקציות להאזנה ל-`clip-ready` ושליחת `deck-trigger`.

### תצוגת Stream Deck (עבור הסטרימר):
- [ ] יצירת `pages/Deck.jsx` עם UI ברשת (Grid) המדמה Stream Deck פיזי.
- [ ] בניית הקומפוננטה `DeckButton.jsx` התומכת במצבי Idle ו-Recording (חיווי ויזואלי מהבהב).
- [ ] יישום הלוגיקה של לחיצת כפתור: שליחת סטטוס (התחלה/עצירה), קטגוריה, ובחירת איכות לשרת דרך ה-Socket.
- [ ] הוספת טיימר הקלטה רץ על המסך.

### תצוגת Editor (עבור העורכים):
- [ ] יצירת `pages/Editor.jsx` והטמעת בסיס עורך הווידאו (חיבור ל-OpenReel).
- [ ] רישום מאזין `onNewClipReceived` כדי לקבל בזמן אמת קליפים חדשים שעלו לשרת.
- [ ] הוספת פונקציונליות המזריקה את הקליפ החדש אל תוך ה-Asset Manager או ה-Timeline של OpenReel אוטומטית.

### ייצוא ופרסום (YouTube):
- [ ] בניית הלוגיקה וה-UI עבור ייצוא הווידאו (`handleExport`).
- [ ] יצירת המודאל `components/YouTubeModal.jsx` (שדות: כותרת, תיאור, פרטיות).
- [ ] חיבור מודאל היוטיוב לבקשת `POST` מול השרת לכתובת `/api/youtube/publish`, והצגת חיווי הצלחה/שגיאה למשתמש.