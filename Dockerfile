FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /bot

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install .

RUN adduser --uid 1063 --disabled-password --gecos "" queuer \
    && mkdir -p /bot/data \
    && chown -R queuer:queuer /bot

USER queuer

CMD ["python3", "-m", "queuer"]

