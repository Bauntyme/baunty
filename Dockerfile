# Python 3.12 slim asosidagi rasm
FROM python:3.12-slim

# Ishchi papka
WORKDIR /app

# Tizim paketlari (ffmpeg audio va video qayta ishlash uchun zarur)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Talablar faylini ko'chirish va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodlarini ko'chirish
COPY . .

# Ma'lumotlar va yuklamalar papkalarini yaratish
RUN mkdir -p data temp_downloads logs

# Botni ishga tushirish
CMD ["python", "main.py"]
