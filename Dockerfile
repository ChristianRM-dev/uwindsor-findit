FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps (postgres client libs + build tools for common python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tree \
    git \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user for dev (optional but recommended)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid ${USER_GID} ${USERNAME} \
  && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} \
  && mkdir -p /workspace \
  && chown -R ${USERNAME}:${USERNAME} /workspace

WORKDIR /workspace

# Install dependencies early (will be fast due to layer caching)
COPY requirements ./requirements
RUN python -m pip install --upgrade pip \
  && pip install -r requirements/dev.txt

USER ${USERNAME}
