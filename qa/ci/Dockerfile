# Disposable test image. Not the production image and never published.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    -c /opt/kamera/requirements-rc.constraints.txt pytest httpx tinycss2
WORKDIR /checkout
ENTRYPOINT []
CMD ["python", "-m", "pytest"]
