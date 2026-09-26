#!/bin/bash
echo "========================================================"
echo "  LiveEdits Streamer Client - התקנה והפעלה"
echo "========================================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "❌ לא נמצא python3 במחשב."
    exit 1
fi

echo "📦 מתקין תלויות נדרשות..."
pip install flask requests obsws-python > /dev/null 2>&1 || pip3 install flask requests obsws-python

echo "🚀 מפעיל את אפליקציית הסטרימר..."
echo "🌐 כתובת הממשק: http://127.0.0.1:5050"
python3 streamer_agent.py
