FROM python:3.12-slim-bookworm

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        coreutils \
        ffmpeg \
        libimage-exiftool-perl \
        rsync \
        tini \
        tzdata \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/kamera

COPY requirements.txt /opt/kamera/requirements.txt

RUN pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        -r /opt/kamera/requirements.txt

COPY app /opt/kamera/app

RUN mkdir -p \
        /config \
        /database \
        /logs \
        /workspace \
        /main-library \
        /sources/import \
        /sources/nas \
        /sources/removable \
    && chown -R 568:568 \
        /opt/kamera \
        /config \
        /database \
        /logs \
        /workspace \
        /sources

USER 568:568

EXPOSE 8080

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=20s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=5)"

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
