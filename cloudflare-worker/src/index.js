// LiveEdits Cloudflare Worker Gateway
// משרת את ממשק ה-Web ומנתב בקשות ל-API

const LANDING_PAGE_HTML = `<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LiveEdits Cloud Hub 🎬</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { font-family: 'Assistant', sans-serif; background: linear-gradient(135deg, #0b0f19 0%, #1e1b4b 50%, #0b0f19 100%); }
    </style>
</head>
<body class="min-h-screen text-slate-100 flex flex-col justify-between p-6">

    <!-- Header -->
    <header class="max-w-6xl mx-auto w-full flex items-center justify-between py-4 border-b border-indigo-900/50">
        <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white text-2xl shadow-lg shadow-indigo-500/30">
                <i class="fa-solid fa-clapperboard"></i>
            </div>
            <div>
                <h1 class="text-xl font-bold tracking-tight text-white">LiveEdits Hub</h1>
                <p class="text-xs text-indigo-300">Cloudflare Edge Gateway</p>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Edge Active
            </span>
        </div>
    </header>

    <!-- Hero Content -->
    <main class="max-w-4xl mx-auto w-full text-center py-12 flex flex-col items-center">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-6">
            <i class="fa-solid fa-bolt"></i> מערכת חכמה לשידורי לייב ועריכה בזמן אמת
        </div>

        <h2 class="text-4xl md:text-5xl font-extrabold text-white leading-tight mb-4">
            עריכת וידאו וקליפים ב-4K <br><span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-sky-400">ישירות מהענן למחשב הסטרימר</span>
        </h2>
        
        <p class="text-base text-slate-300 max-w-2xl mb-10 leading-relaxed">
            פורטל הגישה המרכזי של LiveEdits מבוסס Cloudflare Workers. 
            מערכת זו מחברת בין ה-Streamer Agent שמקליט ב-OBS לבין עורכי הווידאו המרוחקים בלייב.
        </p>

        <!-- Action Cards Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 w-full text-right mb-12">
            <!-- Card 1 -->
            <div class="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur hover:border-indigo-500/50 transition">
                <div class="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center text-lg mb-4">
                    <i class="fa-solid fa-gamepad"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-1">Stream Deck מקומי</h3>
                <p class="text-xs text-slate-400 mb-4">ממשק כפתורים פשוט לסמארטפון/טאבלט להפעלת הקלטות ואירועים ישירות ל-OBS.</p>
                <div class="text-xs text-indigo-400 font-semibold">פורט מקומי 5050</div>
            </div>

            <!-- Card 2 -->
            <div class="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur hover:border-sky-500/50 transition">
                <div class="w-10 h-10 rounded-xl bg-sky-600/20 text-sky-400 flex items-center justify-center text-lg mb-4">
                    <i class="fa-solid fa-film"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-1">חיתוך וחלוקת 4K Grid</h3>
                <p class="text-xs text-slate-400 mb-4">קובץ 4K אחד מפוצל אוטומטית ל-4 ערוצים: מצלמה, משחק, התראות וסאונד.</p>
                <div class="text-xs text-sky-400 font-semibold">מנוע FFmpeg היברידי</div>
            </div>

            <!-- Card 3 -->
            <div class="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur hover:border-emerald-500/50 transition">
                <div class="w-10 h-10 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-lg mb-4">
                    <i class="fa-brands fa-youtube"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-1">העלאה ליוטיוב בלחיצה</h3>
                <p class="text-xs text-slate-400 mb-4">ייצוא ישיר מתוך OpenReel Timeline ופרסום מהיר עם תיאור ותגיות.</p>
                <div class="text-xs text-emerald-400 font-semibold">YouTube Data API v3</div>
            </div>
        </div>

        <!-- Connection Status -->
        <div id="statusBox" class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 w-full max-w-xl text-center">
            <h4 class="text-sm font-bold text-slate-300 mb-2">סטטוס חיבור לשרת המקומי</h4>
            <p id="backendStatus" class="text-xs text-amber-400 mb-4">בודק קישוריות לשרת LiveEdits...</p>
            <div class="flex justify-center gap-3">
                <button onclick="checkConnection()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2 rounded-xl transition cursor-pointer">
                    <i class="fa-solid fa-arrows-rotate ml-1"></i> בדוק שוב
                </button>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="max-w-6xl mx-auto w-full text-center py-4 border-t border-indigo-900/30 text-xs text-slate-500">
        LiveEdits • Powered by Cloudflare Workers & GitHub CI/CD
    </footer>

    <script>
        async function checkConnection() {
            const el = document.getElementById('backendStatus');
            el.className = 'text-xs text-sky-400';
            el.textContent = 'מתחבר ל-API...';
            try {
                const res = await fetch('/api/health');
                if (res.ok) {
                    const data = await res.json();
                    el.className = 'text-xs text-emerald-400 font-bold';
                    el.textContent = '🟢 השרת מחובר ופעיל בהצלחה! (' + (data.status || 'OK') + ')';
                } else {
                    throw new Error('Server returned ' + res.status);
                }
            } catch(e) {
                el.className = 'text-xs text-amber-400';
                el.textContent = '🟡 Worker Edge פעיל. (שרת המקור המקומי יסונכרן דרך Tunnel/Proxy)';
            }
        }
        checkConnection();
    </script>
</body>
</html>
`;

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);

        // ניתוב דף הבית
        if (url.pathname === '/' || url.pathname === '/index.html') {
            return new Response(LANDING_PAGE_HTML, {
                headers: {
                    'content-type': 'text/html;charset=UTF-8',
                    'Cache-Control': 'public, max-age=60'
                }
            });
        }

        // בדיקת Health Check של ה-Worker
        if (url.pathname === '/api/health') {
            return new Response(JSON.stringify({
                status: 'ok',
                service: 'LiveEdits Cloudflare Worker',
                region: request.cf?.colo || 'edge',
                timestamp: new Date().toISOString()
            }), {
                headers: {
                    'content-type': 'application/json',
                    'access-control-allow-origin': '*'
                }
            });
        }

        // אפשרות ניתוב פרוקסי לשרת Backend מקומי (אם מוגדר)
        if (env.BACKEND_ORIGIN && url.pathname.startsWith('/api/')) {
            try {
                const backendUrl = new URL(url.pathname + url.search, env.BACKEND_ORIGIN);
                const proxyRequest = new Request(backendUrl, request);
                return await fetch(proxyRequest);
            } catch (err) {
                return new Response(JSON.stringify({
                    error: 'Backend proxy unreachable',
                    message: err.message
                }), {
                    status: 502,
                    headers: { 'content-type': 'application/json' }
                });
            }
        }

        return new Response('Not Found', { status: 404 });
    }
};
