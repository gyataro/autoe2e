FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    AUTOE2E_CONTAINER=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini \
        xvfb \
        x11vnc \
        novnc \
        websockify \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/bash autoe2e

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen \
    && chown -R autoe2e:autoe2e /app

USER autoe2e
EXPOSE 6080

ENTRYPOINT ["tini", "--"]
CMD ["uv", "run", "--no-sync", "python", "main.py"]
