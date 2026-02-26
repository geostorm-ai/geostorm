FROM python:3.11-slim

# Install Node.js 20 and pnpm
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g pnpm && \
    apt-get purge -y curl && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Build frontend
COPY web/ ./web/
WORKDIR /app/web
RUN CI=true pnpm install --frozen-lockfile
RUN pnpm build
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Version info baked at build time
ARG APP_VERSION=dev
ARG BUILD_TIME
ENV APP_VERSION=${APP_VERSION}
ENV BUILD_TIME=${BUILD_TIME}

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
