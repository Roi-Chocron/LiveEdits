FROM python:3.11-slim

# התקנת ffmpeg וכלים נחוצים
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# העתקת דרישות והתקנתן
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קבצי הפרויקט
COPY . .

# יצירת התיקיות הנדרשות אם חסרות
RUN mkdir -p thumbnails exports drafts uploads

EXPOSE 4000

ENV PORT=4000
ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]
