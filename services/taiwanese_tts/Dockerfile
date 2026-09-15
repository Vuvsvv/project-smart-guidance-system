FROM python:3.10-slim
WORKDIR /app

# ffmpeg 用於 m4a 轉檔，libsndfile1 給 soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY prompts ./prompts
COPY data ./data

# GPU 的部分在宿主機的 GPT-SoVITS api_v2，本服務只是 HTTP client
ENV GSV_API=http://host.docker.internal:9880

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
