import pages from './pages.json';

// מסד נתונים פנימי בזיכרון של ה-Worker
let users = [
  { id: 1, username: "streamer", password: "streamer123", display_name: "עודד (סטרימר)", role: "streamer" },
  { id: 2, username: "editor1", password: "editor123", display_name: "דניאל (עורך)", role: "editor" },
  { id: 3, username: "editor2", password: "editor123", display_name: "אבני (עורך)", role: "editor" }
];

let sessions = new Map();

let recordings = [
  {
    id: "rec-1",
    file_name: "4k_reaction_gameplay.mp4",
    project_name: "ריאקשן וגיימינג לייב",
    button_used: "ריאקשן",
    date_time: "2026-09-26 20:15:00",
    last_edited: "לפני כמה דקות",
    duration: "00:04:32",
    thumbnail: "",
    status: "pending"
  },
  {
    id: "rec-2",
    file_name: "drama_clip_highlight.mp4",
    project_name: "היילייט דרמה מיוחד",
    button_used: "דרמה",
    date_time: "2026-09-26 19:40:00",
    last_edited: "לפני שעה",
    duration: "00:01:45",
    thumbnail: "",
    status: "editing"
  },
  {
    id: "rec-3",
    file_name: "ready_export_youtube.mp4",
    project_name: "קליפ מוכן ליוטיוב",
    button_used: "גיימינג",
    date_time: "2026-09-26 18:20:00",
    last_edited: "היום",
    duration: "00:02:10",
    thumbnail: "",
    status: "ready"
  }
];

function getSessionUser(request) {
  const cookieHeader = request.headers.get("Cookie") || "";
  const match = cookieHeader.match(/session_token=([^;]+)/);
  const token = match ? match[1] : request.headers.get("X-Session-Token");
  if (token && sessions.has(token)) {
    return sessions.get(token);
  }
  return null;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // טיפול ב-CORS
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "*"
        }
      });
    }

    // 1. עמוד התחברות
    if (url.pathname === "/login") {
      return new Response(pages.login, {
        headers: { "Content-Type": "text/html;charset=UTF-8" }
      });
    }

    // 2. עמוד הבית / הדשבורד הראשי
    if (url.pathname === "/" || url.pathname === "/home") {
      const user = getSessionUser(request);
      if (!user) {
        return Response.redirect(`${url.origin}/login?next=${url.pathname}`, 302);
      }
      return new Response(pages.home, {
        headers: { "Content-Type": "text/html;charset=UTF-8" }
      });
    }

    // 3. עמוד ה-Stream Deck
    if (url.pathname === "/deck") {
      const user = getSessionUser(request);
      if (!user) {
        return Response.redirect(`${url.origin}/login?next=/deck`, 302);
      }
      return new Response(pages.deck, {
        headers: { "Content-Type": "text/html;charset=UTF-8" }
      });
    }

    // 4. API: סטטוס שטח אחסון בשרת
    if (url.pathname === "/api/storage-info") {
      return new Response(JSON.stringify({
        status: "success",
        total_gb: 100.0,
        used_gb: 34.5,
        free_gb: 65.5,
        percent_used: 34.5
      }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 5. API: הורדת אפליקציית הסטרימר
    if (url.pathname === "/api/download/streamer-client") {
      return Response.redirect("https://github.com/Roi-Chocron/LiveEdits/releases/download/latest/LiveEdits_Streamer_Client.exe", 302);
    }

    // 6. API: התחברות
    if (url.pathname === "/api/auth/login" && request.method === "POST") {
      try {
        const body = await request.json();
        const found = users.find(u => u.username === body.username && u.password === body.password);
        if (found) {
          const token = "token-" + Math.random().toString(36).substring(2) + Date.now();
          sessions.set(token, {
            id: found.id,
            username: found.username,
            display_name: found.display_name,
            role: found.role
          });

          return new Response(JSON.stringify({
            status: "success",
            user: {
              id: found.id,
              username: found.username,
              display_name: found.display_name,
              role: found.role
            },
            redirect_to: found.role === "streamer" ? "/deck" : "/home"
          }), {
            headers: {
              "Content-Type": "application/json",
              "Set-Cookie": `session_token=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`
            }
          });
        }
        return new Response(JSON.stringify({ status: "error", message: "שם משתמש או סיסמה שגויים" }), {
          status: 401,
          headers: { "Content-Type": "application/json" }
        });
      } catch (e) {
        return new Response(JSON.stringify({ status: "error", message: "שגיאה בבקשה" }), { status: 400 });
      }
    }

    // 7. API: משתמש נוכחי
    if (url.pathname === "/api/auth/me") {
      const user = getSessionUser(request);
      if (user) {
        return new Response(JSON.stringify({ status: "success", user }), {
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ status: "unauthenticated", user: null }), {
        status: 401,
        headers: { "Content-Type": "application/json" }
      });
    }

    // 8. API: התנתקות
    if (url.pathname === "/api/auth/logout") {
      return new Response(null, {
        status: 302,
        headers: {
          "Location": "/login",
          "Set-Cookie": "session_token=; Path=/; Max-Age=0"
        }
      });
    }

    // 9. API: רשימת עורכים
    if (url.pathname === "/api/users/editors") {
      const editors = users.filter(u => u.role === "editor").map(e => ({
        id: e.id,
        username: e.username,
        display_name: e.display_name,
        role: e.role,
        is_active: true
      }));
      return new Response(JSON.stringify(editors), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 10. API: רשימת הקלטות
    if (url.pathname === "/api/recordings") {
      return new Response(JSON.stringify(recordings), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 11. API: קבלת העלאת הקלטה מ-Streamer Client
    if (url.pathname === "/api/recordings/upload" && request.method === "POST") {
      return new Response(JSON.stringify({
        status: "success",
        message: "ההקלטה נקלטה בהצלחה בענן והועברה לעורכים"
      }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 12. API: שליטת Stream Deck (Control)
    if (url.pathname === "/control" && request.method === "POST") {
      const body = await request.json();
      const action = body.action;

      if (["ריאקשן", "דרמה", "גיימינג", "אחר", "חפיפה"].includes(action)) {
        recordings.unshift({
          id: "rec-" + Date.now(),
          file_name: `grid_record_${action}_${Date.now()}.mp4`,
          project_name: `הקלטת ${action}`,
          button_used: action,
          date_time: new Date().toLocaleString("he-IL"),
          last_edited: "זה עתה",
          duration: "00:00:30",
          thumbnail: "",
          status: "pending"
        });
        return new Response(JSON.stringify({ status: "success", message: `ההקלטה התחילה עבור: ${action}` }), {
          headers: { "Content-Type": "application/json" }
        });
      }

      if (action === "השהיה/המשך") {
        return new Response(JSON.stringify({ status: "success", message: "מצב הקלטה עודכן" }), {
          headers: { "Content-Type": "application/json" }
        });
      }

      if (action === "סיום וחזרה" || action === "סיום בלבד") {
        return new Response(JSON.stringify({ status: "success", message: "הקלטה נשמרה בהצלחה והועברה לעורכים" }), {
          headers: { "Content-Type": "application/json" }
        });
      }

      return new Response(JSON.stringify({ status: "error", message: "פעולה לא נתמכת" }), { status: 400 });
    }

    // 13. תבנית OBS
    if (url.pathname === "/api/obs-template" || url.pathname === "/live-edits-obs-template.json") {
      return new Response(JSON.stringify({ message: "OBS 4K Grid Template" }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 14. הגדרת קאנבס 4K
    if (url.pathname === "/api/obs/setup-canvas") {
      return new Response(JSON.stringify({ status: "success", message: "קאנבס 4K עודכן בהצלחה" }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response("Not Found", { status: 404 });
  }
};
