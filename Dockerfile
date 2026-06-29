# 线上环境若拉不到 3.11，使用 3.10-slim；构建时需配置 HTTP 代理
FROM python:3.10-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/chroma

# 构建完成后清除代理，避免影响容器运行时访问大模型 API
ENV HTTP_PROXY= \
    HTTPS_PROXY= \
    NO_PROXY=

ENV HOST=0.0.0.0 \
    PORT=8080 \
    RELOAD=false \
    LOG_LEVEL=INFO

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

CMD ["python", "app.py"]
