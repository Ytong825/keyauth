# KeyAuth · 卡密授权系统
# 零依赖，基于 python:slim，镜像约 130MB
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KEYAUTH_DATA=/data \
    PORT=8787 \
    BIND=0.0.0.0

WORKDIR /app

COPY server.py ./
COPY kauth/ ./kauth/
COPY static/ ./static/

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=3).status==200 else 1)"

CMD ["python", "server.py"]
