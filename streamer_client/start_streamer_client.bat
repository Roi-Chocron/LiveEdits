@echo off
chcp 65001 >nul
echo ========================================================
echo   LiveEdits Streamer Client - התקנה והפעלה מהירה
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] לא נמצא Python מותקן במחשב.
    echo אנא הורד והתקן Python מ: https://www.python.org/downloads/
    pause
    exit /b
)

echo [*] מתקין תלויות נדרשות (Flask, requests, obsws-python)...
pip install flask requests obsws-python >nul 2>&1

echo [*] מפעיל את אפליקציית הסטרימר...
echo [*] הממשק ייפתח בדפדפן בכתובת: http://127.0.0.1:5050
echo.
start http://127.0.0.1:5050
python streamer_agent.py
pause
