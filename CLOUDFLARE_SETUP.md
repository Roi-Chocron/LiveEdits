# מדריך חיבור LiveEdits לענן באמצעות Cloudflare Tunnel (חינמי לחלוטין 100%) ☁️🚀

שרת **LiveEdits** מבצע עריכות וידאו מקומיות, חיתוכי FFmpeg והקלטות OBS. 
הדרך המהירה, המאובטחת והחינמית לחלוטין לחשוף אותו לאינטרנט (לעורכים מרוחקים או לגישה מבחוץ) ללא צורך בתשלום על שרתי ענן יקרים וללא פתיחת פורטים בראוטר (Port Forwarding), היא **Cloudflare Tunnel**.

---

## שלב 1: התחברות ל-Cloudflare (חד פעמי)
הרץ בטרמינל את הפקודה:
```bash
cloudflared tunnel login
```
ייפתח חלון בדפדפן שיבקש ממך לבחור את הדומיין החינמי/הקיים שלך ב-Cloudflare ולאשר את החיבור.

---

## שלב 2: יצירת המנהרה (Tunnel)
לאחר ההתחברות, צור מנהרה חדשה בשם `liveedits`:
```bash
cloudflared tunnel create liveedits
```
הפקודה תיצור מזהה מנהרה (UUID) וקובץ אישורי גישה בתיקיית `~/.cloudflared/<UUID>.json`.

---

## שלב 3: הגדרת קובץ התצורה (`config.yml`)
צור קובץ בשם `~/.cloudflared/config.yml` עם התוכן הבא (החלף את ה-UUID והדומיין):
```yaml
tunnel: <UUID_של_המנהרה>
credentials-file: /home/roi/.cloudflared/<UUID_של_המנהרה>.json

ingress:
  - hostname: liveedits.yourdomain.com
    service: http://localhost:4000
  - service: http_status:404
```

---

## שלב 4: ניתוב הדומיין ב-DNS
הרץ פקודה המקשרת את הדומיין שלך למנהרה:
```bash
cloudflared tunnel route dns liveedits liveedits.yourdomain.com
```

---

## שלב 5: הרצת המנהרה
בכל פעם שתרצה שהשרת יהיה זמין ברשת:
```bash
cloudflared tunnel run liveedits
```
או להפעיל אותה כשירות קבוע במערכת (System Service):
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
```

---

## ⚡ חלופה מהירה (Quick Tunnel - ללא דומיין אישי וללא הגדרות)
אם תרצה קישור מיידי וחינמי של Cloudflare (למשל `https://xxxx.trycloudflare.com`):
```bash
cloudflared tunnel --url http://localhost:4000
```
יווצר לך קישור מאובטח (HTTPS) זמני שמאפשר לכל עורך בעולם להתחבר ישירות למערכת שלך!
