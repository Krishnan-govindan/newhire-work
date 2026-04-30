# NewHire.work — production image for Railway.
#
# Builds the Reboot Python backend + the React skill-tree UI, then
# runs `rbt serve run --config=production` listening on $PORT.

# ---------- Stage 1: build ----------
FROM python:3.10-slim-bookworm AS build

# Install Node 20 (for the React build) and basic build tools.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg build-essential \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Install uv (Astral's Python package manager).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy dependency manifests first for better layer caching.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# Copy the rest of the project.
COPY .rbtrc ./
COPY api/ ./api/
COPY backend/ ./backend/
COPY web/package.json web/package-lock.json ./web/
COPY web/tsconfig.json web/tsconfig.app.json web/tsconfig.node.json \
     web/vite.config.ts ./web/
COPY web/ui/ ./web/ui/

# First rbt generate — produces backend stubs.
RUN uv run rbt generate

# Install web deps then run rbt generate again so React bindings
# pick up the now-present node_modules.
RUN cd web && npm ci
RUN uv run rbt generate

# Build the React UI bundles into web/dist/.
RUN cd web && npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.10-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive
# Reboot runs the application as a Python module — Node is not
# needed at runtime, only at build time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install uv at runtime so we can `uv run rbt serve run`.
RUN python -m pip install --no-cache-dir uv

WORKDIR /app

# Copy the synced virtualenv, generated code, built UI, and source.
COPY --from=build /app/.venv ./.venv
COPY --from=build /app/pyproject.toml /app/uv.lock /app/.python-version \
     /app/.rbtrc ./
COPY --from=build /app/api ./api
COPY --from=build /app/backend ./backend
COPY --from=build /app/web/dist ./web/dist
COPY --from=build /app/web/api ./web/api
# Vite config is referenced by tsconfig but not needed at runtime;
# ui sources are not needed either.

# Persistent state directory for Reboot. On Railway, mount a Volume
# at /data to survive deploys; without one, state resets per deploy.
ENV RBT_STATE_DIRECTORY=/data
RUN mkdir -p /data

# Railway sets $PORT. Reboot reads --port=$PORT or env PORT.
ENV PORT=8080
EXPOSE 8080

# Use shell form so $PORT expands at runtime.
CMD uv run rbt serve run --config=production --port=${PORT} \
        --state-directory=${RBT_STATE_DIRECTORY}
