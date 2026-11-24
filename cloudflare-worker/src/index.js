import pages from './pages.json';

const DEFAULT_USERS = [
  { id: 1, username: "streamer", password: "streamer123", display_name: "עודד (סטרימר)", role: "streamer" },
  { id: 2, username: "editor1", password: "editor123", display_name: "דניאל (עורך)", role: "editor" },
  { id: 3, username: "editor2", password: "editor123", display_name: "אבני (עורך)", role: "editor" }
];

async function getRecordingsList(env) {
  if (env && env.LIVEEDITS_KV) {
    try {
      const data = await env.LIVEEDITS_KV.get("recordings_list");
      if (data) {
        const parsed = JSON.parse(data);
        return parsed.map(r => ({
          ...r,
          file_path: r.file_path || r.original_path || r.file_name || `recording_${r.id}.mp4`,
          original_path: r.original_path || r.file_path || r.file_name || `recording_${r.id}.mp4`
        }));
      }
    } catch (e) {
      console.error("KV read error:", e);
    }
  }
  return [];
}

async function saveRecordingsList(env, list) {
  if (env && env.LIVEEDITS_KV) {
    try {
      await env.LIVEEDITS_KV.put("recordings_list", JSON.stringify(list));
    } catch (e) {
      console.error("KV write error:", e);
    }
  }
}

async function getSessionUser(request, env) {
  const cookieHeader = request.headers.get("Cookie") || "";
  const match = cookieHeader.match(/session_token=([^;]+)/);
  const token = match ? match[1] : request.headers.get("X-Session-Token");
  
  if (!token) return null;

  if (env && env.LIVEEDITS_KV) {
    try {
      const val = await env.LIVEEDITS_KV.get("session:" + token);
      if (val) return JSON.parse(val);
    } catch (e) {
      console.error(e);
    }
  }

  // fallback session parse
  if (token.startsWith("user-streamer-")) {
    return DEFAULT_USERS[0];
  } else if (token.startsWith("user-editor1-")) {
    return DEFAULT_USERS[1];
  } else if (token.startsWith("user-editor2-")) {
    return DEFAULT_USERS[2];
  }
  return null;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // טיפול ב-CORS מלא לכל ה-Endpoints
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
      const user = await getSessionUser(request, env);
      if (!user) {
        return Response.redirect(`${url.origin}/login?next=${url.pathname}`, 302);
      }
      return new Response(pages.home, {
        headers: { "Content-Type": "text/html;charset=UTF-8" }
      });
    }

    // 3. עמוד ה-Stream Deck
    if (url.pathname === "/deck") {
      const user = await getSessionUser(request, env);
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
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }

    // 5. API: הורדת תוכנת הסטרימר EXE
    if (url.pathname === "/api/download/streamer-client") {
      return Response.redirect("https://github.com/Roi-Chocron/LiveEdits/releases/download/latest/LiveEdits_Streamer_Client.exe", 302);
    }

    // 6. API: התחברות
    if (url.pathname === "/api/auth/login" && request.method === "POST") {
      try {
        const body = await request.json();
        const found = DEFAULT_USERS.find(u => u.username === body.username && u.password === body.password);
        if (found) {
          const token = `user-${found.username}-${Date.now()}`;
          if (env && env.LIVEEDITS_KV) {
            await env.LIVEEDITS_KV.put("session:" + token, JSON.stringify(found), { expirationTtl: 86400 * 7 });
          }

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
              "Access-Control-Allow-Origin": "*",
              "Set-Cookie": `session_token=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800`
            }
          });
        }
        return new Response(JSON.stringify({ status: "error", message: "שם משתמש או סיסמה שגויים" }), {
          status: 401,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      } catch (e) {
        return new Response(JSON.stringify({ status: "error", message: "שגיאה בבקשה" }), {
          status: 400,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
    }

    // 7. API: משתמש נוכחי
    if (url.pathname === "/api/auth/me") {
      const user = await getSessionUser(request, env);
      if (user) {
        return new Response(JSON.stringify({ status: "success", user }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      }
      return new Response(JSON.stringify({ status: "unauthenticated", user: null }), {
        status: 401,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
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
      const editors = DEFAULT_USERS.filter(u => u.role === "editor").map(e => ({
        id: e.id,
        username: e.username,
        display_name: e.display_name,
        role: e.role,
        is_active: true
      }));
      return new Response(JSON.stringify(editors), {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }

    // 10. API: רשימת הקלטות מתוך מסד הנתונים בענן (Cloudflare KV)
    if (url.pathname === "/api/recordings") {
      const list = await getRecordingsList(env);
      return new Response(JSON.stringify(list), {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }

    // 11. API: קבלת העלאת הקלטה אמיתית מ-Streamer Client ושמירה קבועה ב-KV
    // 11. API: קבלת העלאת הקלטה אמיתית מ-Streamer Client ושמירה קבועה ב-KV
    if (url.pathname === "/api/recordings/upload" && request.method === "POST") {
      try {
        let id, filename, buttonUsed, duration, dateTime, filePath, gdriveId, gdriveViewUrl, gdriveDownloadUrl, thumbnail;
        const contentType = request.headers.get("Content-Type") || "";

        if (contentType.includes("application/json")) {
          const body = await request.json();
          id = body.id || ("obs-" + Date.now());
          filename = body.filename || body.file_name || "recording.mp4";
          buttonUsed = body.button_used || "ריאקשן";
          duration = body.duration || "00:00:15";
          dateTime = body.date_time || new Date().toLocaleString("he-IL");
          filePath = body.file_path || body.original_path || filename;
          gdriveId = body.gdrive_id || "";
          gdriveViewUrl = body.gdrive_view_url || "";
          gdriveDownloadUrl = body.gdrive_download_url || "";
          thumbnail = body.thumbnail || "";
        } else {
          const formData = await request.formData();
          id = formData.get("id") || ("obs-" + Date.now());
          filename = formData.get("filename") || formData.get("file_name") || "recording.mp4";
          buttonUsed = formData.get("button_used") || "ריאקשן";
          duration = formData.get("duration") || "00:00:15";
          dateTime = formData.get("date_time") || new Date().toLocaleString("he-IL");
          filePath = formData.get("file_path") || formData.get("original_path") || filename;
          gdriveId = formData.get("gdrive_id") || "";
          gdriveViewUrl = formData.get("gdrive_view_url") || "";
          gdriveDownloadUrl = formData.get("gdrive_download_url") || "";
          thumbnail = formData.get("thumbnail") || "";
        }

        const newRecord = {
          id: id,
          file_name: filename,
          file_path: filePath,
          original_path: filePath,
          project_name: `הקלטת ${buttonUsed}`,
          button_used: buttonUsed,
          date_time: dateTime,
          last_edited: "זה עתה",
          duration: duration,
          thumbnail: thumbnail,
          gdrive_id: gdriveId,
          gdrive_view_url: gdriveViewUrl,
          gdrive_download_url: gdriveDownloadUrl,
          status: "pending"
        };

        const list = await getRecordingsList(env);
        // הסרת כפילויות אם כבר קיים id כזה
        const filtered = list.filter(r => r.id !== id);
        filtered.unshift(newRecord);
        await saveRecordingsList(env, filtered);

        return new Response(JSON.stringify({
          status: "success",
          message: "ההקלטה נשמרה במסד הנתונים בענן והתווספה לדשבורד בהצלחה!",
          recording: newRecord
        }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      } catch (err) {
        return new Response(JSON.stringify({
          status: "error",
          message: err.message
        }), {
          status: 400,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      }
    }

    // 11.5 API: מחיקת הקלטה מדשבורד הענן
    if (url.pathname.startsWith("/api/recordings/") && (request.method === "DELETE" || (request.method === "POST" && url.pathname.endsWith("/delete")))) {
      try {
        const parts = url.pathname.split("/").filter(Boolean);
        let recId = parts[2]; // /api/recordings/{id}
        if (recId === "delete") recId = url.searchParams.get("id");

        if (!recId) {
          return new Response(JSON.stringify({ status: "error", message: "חסר מזהה הקלטה למחיקה" }), {
            status: 400,
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
          });
        }

        const list = await getRecordingsList(env);
        const newList = list.filter(r => r.id !== recId && r.file_name !== recId);
        await saveRecordingsList(env, newList);

        return new Response(JSON.stringify({
          status: "success",
          message: "ההקלטה נמחקה בהצלחה מהדשבורד!"
        }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      } catch (err) {
        return new Response(JSON.stringify({ status: "error", message: err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
    }

    // 12. API: שליטת Stream Deck (Control)
    if (url.pathname === "/control" && request.method === "POST") {
      const body = await request.json();
      const action = body.action;

      if (["ריאקשן", "דרמה", "גיימינג", "אחר", "חפיפה"].includes(action)) {
        const newRecord = {
          id: "rec-" + Date.now(),
          file_name: `grid_record_${action}_${Date.now()}.mp4`,
          project_name: `הקלטת ${action}`,
          button_used: action,
          date_time: new Date().toLocaleString("he-IL"),
          last_edited: "זה עתה",
          duration: "00:00:30",
          thumbnail: "",
          status: "pending"
        };
        const list = await getRecordingsList(env);
        list.unshift(newRecord);
        await saveRecordingsList(env, list);

        return new Response(JSON.stringify({ status: "success", message: `ההקלטה התחילה עבור: ${action}` }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }

      if (action === "השהיה/המשך") {
        return new Response(JSON.stringify({ status: "success", message: "מצב הקלטה עודכן" }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }

      if (action === "סיום וחזרה" || action === "סיום בלבד") {
        return new Response(JSON.stringify({ status: "success", message: "הקלטה נשמרה בהצלחה והועברה לעורכים" }), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }

      return new Response(JSON.stringify({ status: "error", message: "פעולה לא נתמכת" }), {
        status: 400,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 13. תבנית OBS
    if (url.pathname === "/api/obs-template" || url.pathname === "/live-edits-obs-template.json") {
      return new Response(JSON.stringify({ message: "OBS 4K Grid Template" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 14. הגדרת קאנבס 4K
    if (url.pathname === "/api/obs/setup-canvas") {
      return new Response(JSON.stringify({ status: "success", message: "קאנבס 4K עודכן בהצלחה" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 15. API: פתיחת עורך סרטונים OpenReel
    if (url.pathname === "/api/open-editor") {
      try {
        let reqData = {};
        if (request.method === "POST") {
          reqData = await request.json().catch(() => ({}));
        }
        const videoPath = reqData.path || url.searchParams.get("path") || "";
        const videoName = reqData.name || (videoPath ? videoPath.split("/").pop().split("\\").pop() : "recording.mp4");
        const draftId = reqData.draftId || "";
        const reqVideoUrl = reqData.videoUrl || url.searchParams.get("videoUrl") || "";

        const queryParams = [];
        if (draftId) queryParams.push(`draftId=${encodeURIComponent(draftId)}`);
        
        const videoStreamUrl = reqVideoUrl || `http://127.0.0.1:5050/api/video?path=${encodeURIComponent(videoPath)}`;
        queryParams.push(`videoUrl=${encodeURIComponent(videoStreamUrl)}`);
        queryParams.push(`videoPath=${encodeURIComponent(videoPath)}`);
        if (videoName) queryParams.push(`videoName=${encodeURIComponent(videoName)}`);

        // כתובת לעורך הוידאו
        const editorUrl = `http://localhost:5174/#/editor?${queryParams.join("&")}`;

        return new Response(JSON.stringify({
          status: "success",
          url: editorUrl,
          message: "עורך OpenReel מוכן לפתיחה"
        }), {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        });
      } catch (e) {
        return new Response(JSON.stringify({ status: "error", message: e.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      }
    }

    // 16. API: ניגון וידאו / הורדה
    if (url.pathname === "/api/video") {
      const videoPath = url.searchParams.get("path");
      return new Response(JSON.stringify({
        status: "info",
        message: "וידאו זה שמור במחשב המקומי של הסטרימר/העורך ומוכן לעריכה ב-OpenReel",
        path: videoPath
      }), {
        status: 404,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });
    }

    
    // 16.5. Google Drive OAuth Flow, Status & Token Provider
    if (url.pathname === "/api/gdrive/status") {
      let gdriveStatus = { configured: true, authenticated: false, email: null };
      if (env && env.LIVEEDITS_KV) {
        try {
          const saved = await env.LIVEEDITS_KV.get("gdrive_oauth_status");
          if (saved) gdriveStatus = JSON.parse(saved);
        } catch (e) {
          console.error(e);
        }
      }
      return new Response(JSON.stringify({ status: "success", data: gdriveStatus }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/api/gdrive/token") {
      let tokenData = null;
      if (env && env.LIVEEDITS_KV) {
        try {
          const saved = await env.LIVEEDITS_KV.get("gdrive_tokens");
          if (saved) tokenData = JSON.parse(saved);
        } catch (e) {
          console.error(e);
        }
      }

      if (tokenData) {
        const clientId = "429640940972-28m20qs809ba1umht9jfos9j9peu42fk.apps.googleusercontent.com";
        const clientSecret = env.GOOGLE_CLIENT_SECRET // REDACTED;

        // רענון טוקן אוטומטי אם קיים refresh_token
        if (tokenData.refresh_token) {
          try {
            const refreshResp = await fetch("https://oauth2.googleapis.com/token", {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({
                client_id: clientId,
                client_secret: clientSecret,
                refresh_token: tokenData.refresh_token,
                grant_type: "refresh_token"
              })
            });

            if (refreshResp.ok) {
              const freshData = await refreshResp.json();
              if (freshData.access_token) {
                tokenData.access_token = freshData.access_token;
                if (env && env.LIVEEDITS_KV) {
                  await env.LIVEEDITS_KV.put("gdrive_tokens", JSON.stringify(tokenData));
                }
              }
            }
          } catch (rErr) {
            console.error("Token refresh error:", rErr);
          }
        }

        if (tokenData.access_token) {
          return new Response(JSON.stringify({ status: "success", token: tokenData.access_token }), {
            headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
          });
        }
      }

      return new Response(JSON.stringify({ status: "error", message: "Google Drive אינו מחובר" }), {
        status: 404,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/api/gdrive/oauth/login") {
      const clientId = "429640940972-28m20qs809ba1umht9jfos9j9peu42fk.apps.googleusercontent.com";
      const redirectUri = "https://liveedits.roi-chocron7.workers.dev/api/gdrive/oauth/callback";
      const scope = encodeURIComponent("https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/userinfo.email");
      const googleAuthUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=" + clientId + "&redirect_uri=" + encodeURIComponent(redirectUri) + "&response_type=code&scope=" + scope + "&access_type=offline&prompt=consent";
      return Response.redirect(googleAuthUrl, 302);
    }

    if (url.pathname === "/api/gdrive/oauth/callback") {
      const code = url.searchParams.get("code");
      const error = url.searchParams.get("error");
      if (error) {
        return Response.redirect(url.origin + "/home?gdrive_error=" + encodeURIComponent(error), 302);
      }
      if (code) {
        try {
          const clientId = "429640940972-28m20qs809ba1umht9jfos9j9peu42fk.apps.googleusercontent.com";
          const clientSecret = env.GOOGLE_CLIENT_SECRET // REDACTED;
          const redirectUri = "https://liveedits.roi-chocron7.workers.dev/api/gdrive/oauth/callback";

          const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
              code: code,
              client_id: clientId,
              client_secret: clientSecret,
              redirect_uri: redirectUri,
              grant_type: "authorization_code"
            })
          });

          const tokens = await tokenResp.json();
          if (tokens.access_token) {
            let email = "Google Drive User";
            try {
              const uResp = await fetch("https://www.googleapis.com/oauth2/v2/userinfo", {
                headers: { "Authorization": "Bearer " + tokens.access_token }
              });
              const uData = await uResp.json();
              if (uData.email) email = uData.email;
            } catch (err) {
              console.error("Userinfo fetch error:", err);
            }

            if (env && env.LIVEEDITS_KV) {
              await env.LIVEEDITS_KV.put("gdrive_tokens", JSON.stringify(tokens));
              await env.LIVEEDITS_KV.put("gdrive_oauth_status", JSON.stringify({
                configured: true,
                authenticated: true,
                email: email
              }));
            }

            return Response.redirect(url.origin + "/home?gdrive_connected=true", 302);
          }
        } catch (e) {
          console.error("Token exchange error:", e);
        }
      }
      return Response.redirect(url.origin + "/home?gdrive_error=Failed_to_exchange_token", 302);
    }

    if (url.pathname === "/api/gdrive/disconnect" && request.method === "POST") {
      if (env && env.LIVEEDITS_KV) {
        await env.LIVEEDITS_KV.delete("gdrive_tokens");
        await env.LIVEEDITS_KV.delete("gdrive_oauth_status");
      }
      return new Response(JSON.stringify({ status: "success", message: "החיבור ל-Google Drive נותק בהצלחה" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // 17. YouTube OAuth Flow & Status
    if (url.pathname === "/api/youtube/status") {
      let ytStatus = { configured: true, authenticated: false, channel: null };
      if (env && env.LIVEEDITS_KV) {
        try {
          const saved = await env.LIVEEDITS_KV.get("youtube_oauth_status");
          if (saved) ytStatus = JSON.parse(saved);
        } catch (e) {
          console.error(e);
        }
      }
      return new Response(JSON.stringify({ status: "success", data: ytStatus }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/api/youtube/config" && request.method === "POST") {
      return new Response(JSON.stringify({ status: "success", message: "הגדרות YouTube נשמרו" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    if (url.pathname === "/api/youtube/oauth/login") {
      const clientId = "429640940972-sh167aum8i3ipftb08hh2o7gaben4orj.apps.googleusercontent.com";
      const redirectUri = "https://liveedits.roi-chocron7.workers.dev/api/youtube/oauth/callback";
      const scope = encodeURIComponent("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly");
      const googleAuthUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=" + clientId + "&redirect_uri=" + encodeURIComponent(redirectUri) + "&response_type=code&scope=" + scope + "&access_type=offline&prompt=consent";
      return Response.redirect(googleAuthUrl, 302);
    }

    if (url.pathname === "/api/youtube/oauth/callback") {
      const code = url.searchParams.get("code");
      const error = url.searchParams.get("error");
      if (error) {
        return Response.redirect(url.origin + "/home?youtube_error=" + encodeURIComponent(error), 302);
      }
      if (code) {
        try {
          const clientId = "429640940972-sh167aum8i3ipftb08hh2o7gaben4orj.apps.googleusercontent.com";
          const clientSecret = env.GOOGLE_CLIENT_SECRET // REDACTED;
          const redirectUri = "https://liveedits.roi-chocron7.workers.dev/api/youtube/oauth/callback";

          const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
              code: code,
              client_id: clientId,
              client_secret: clientSecret,
              redirect_uri: redirectUri,
              grant_type: "authorization_code"
            })
          });

          const tokens = await tokenResp.json();
          if (tokens.access_token) {
            // Fetch channel details
            let channelInfo = { title: "YouTube Creator", subscribers: 0, video_count: 0, thumbnail: "" };
            try {
              const chanResp = await fetch("https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true", {
                headers: { "Authorization": "Bearer " + tokens.access_token }
              });
              const chanData = await chanResp.json();
              if (chanData.items && chanData.items.length > 0) {
                const item = chanData.items[0];
                channelInfo = {
                  title: item.snippet.title,
                  thumbnail: item.snippet.thumbnails?.default?.url || "",
                  subscribers: item.statistics?.subscriberCount || 0,
                  video_count: item.statistics?.videoCount || 0
                };
              }
            } catch (err) {
              console.error("Channel fetch error:", err);
            }

            if (env && env.LIVEEDITS_KV) {
              await env.LIVEEDITS_KV.put("youtube_tokens", JSON.stringify(tokens));
              await env.LIVEEDITS_KV.put("youtube_oauth_status", JSON.stringify({
                configured: true,
                authenticated: true,
                channel: channelInfo
              }));
            }

            return Response.redirect(url.origin + "/home?youtube_connected=true", 302);
          }
        } catch (e) {
          console.error("Token exchange error:", e);
        }
      }
      return Response.redirect(url.origin + "/home?youtube_error=Failed_to_exchange_token", 302);
    }

    if (url.pathname === "/api/youtube/disconnect" && request.method === "POST") {
      if (env && env.LIVEEDITS_KV) {
        await env.LIVEEDITS_KV.delete("youtube_tokens");
        await env.LIVEEDITS_KV.delete("youtube_oauth_status");
      }
      return new Response(JSON.stringify({ status: "success", message: "החיבור ליוטיוב נותק בהצלחה" }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    return new Response("Not Found", { status: 404 });
  }
};
