FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin \
    KAMERA_SOURCE_HELPER_ENABLED=false \
    KAMERA_DEVICE_NODE_ROOT=/dev/bibliothekar \
    KAMERA_WEB_UID=568 \
    KAMERA_WEB_GID=568

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

ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.revision="${SOURCE_REVISION}"

WORKDIR /opt/kamera

COPY requirements.txt /opt/kamera/requirements.txt
COPY requirements-rc.constraints.txt /opt/kamera/requirements-rc.constraints.txt

RUN pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        -r /opt/kamera/requirements.txt \
        -c /opt/kamera/requirements-rc.constraints.txt

COPY app /opt/kamera/app

RUN mkdir -p \
        /appdata \
        /config \
        /database \
        /logs \
        /workspace \
        /main-library \
        /sources/nas \
        /sources/removable \
    && chown -R 568:568 \
        /config \
        /database \
        /logs \
        /workspace \
        /sources/nas

# 0.31.0 startet absichtlich als root: nur der interne Quellen-Helper
# benoetigt Mount-/Geraeterechte. Der Supervisor startet die eigentliche
# Bibliothekar-Web-App explizit als UID/GID 568.
USER 0:0

EXPOSE 8080

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=20s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=5)"

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["python", "-m", "app.container_supervisor"]
