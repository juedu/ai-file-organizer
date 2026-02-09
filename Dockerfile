FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (Pillow 등)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev libwebp-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY backend/ backend/
COPY frontend/ frontend/
COPY site/ site/
COPY run.py .

# 데이터/설정 볼륨 마운트 포인트
RUN mkdir -p /app/config /app/data/profiles /app/data/manifests

EXPOSE 5001

CMD ["python", "run.py"]
