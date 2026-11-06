# Reviewed official image identities: 2026-10-21. Linux amd64 baseline.
FROM node:22.23.3-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS node_runtime
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOME=/home/ssdl \
    XDG_CACHE_HOME=/app/cache \
    SSDL_CACHE_DIR=/app/cache \
    SSDL_MEDIA_ROOT=/downloads \
    SSDL_CONTAINER=1 \
    SSDL_DOWNLOAD_DIR=/downloads \
    SSDL_PORT=8765

WORKDIR /app

# Freeze OS package sources as well as the base images and Python requirements.
# Keep signature verification; only the historical metadata expiry is disabled.
COPY docker/debian.sources /etc/apt/sources.list.d/ssdl.sources
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg libatomic1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /usr/local/LICENSE /usr/local/share/doc/node/LICENSE

COPY requirements.lock.txt ./
RUN python -m venv /app/.venv \
    && /app/.venv/bin/python -m pip install --no-cache-dir --only-binary=:all: -r requirements.lock.txt \
    && /app/.venv/bin/python -m pip check \
    && mkdir -p /usr/local/share/ssdl \
    && dpkg-query -W > /usr/local/share/ssdl/os-packages.txt \
    && /app/.venv/bin/python -m pip freeze --all > /usr/local/share/ssdl/python-packages.txt \
    && node --version > /usr/local/share/ssdl/node-version.txt

# Explicit runtime sources only; .dockerignore independently bounds the context.
COPY app.py LICENSE THIRD_PARTY_NOTICES.md ./
COPY ssdl/ ./ssdl/
COPY static/ ./static/
COPY chrome-extension/ ./chrome-extension/
COPY docker/entrypoint.py docker/runtime.py docker/storage.py docker/healthcheck.py docker/session_key.py ./docker/

RUN groupadd --gid 10001 ssdl \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/ssdl --shell /usr/sbin/nologin ssdl \
    && mkdir -p /app/data /app/cache /downloads \
    && chown -R 10001:10001 /app/data /app/cache /downloads \
    && chmod 0700 /app/data /app/cache \
    && chmod 0750 /downloads

USER 10001:10001
EXPOSE 8765
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "docker/healthcheck.py"]
CMD ["python", "-u", "docker/entrypoint.py"]
