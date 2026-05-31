# Multi-Agent Dev Intelligence System — container image.
#
# The app talks to its data sources exclusively through the Coral CLI, which it
# launches as an MCP stdio subprocess (`coral mcp-stdio`). So the image needs
# BOTH the Python app and the `coral` binary on PATH.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- System deps + Coral CLI -------------------------------------------------
# curl is needed to fetch the Coral install script. ca-certificates for TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://withcoral.com/install.sh | sh \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Make sure the coral binary is on PATH (the installer drops it in /root/.local
# /bin or /usr/local/bin depending on version; expose both).
ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"

# --- Python deps (cached layer) ----------------------------------------------
COPY requirements.txt ./
RUN pip install -r requirements.txt

# --- App + Coral source specs ------------------------------------------------
COPY app ./app
COPY coral ./coral

# Coral loads source specs relative to its working directory (CORAL_CWD); /app
# contains coral/sources/*.yaml, so the default cwd works out of the box.
EXPOSE 8000

# Webhook senders (GitHub/Sentry/Slack) need an immediate ack, so a single
# worker is fine — the graph runs in a background task. Scale with replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
