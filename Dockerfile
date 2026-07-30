# ============================================================
# RaceOS AI Software Factory — Docker Image
# ============================================================
# Multi-stage build for minimal production image.
#
# Usage:
#   docker build -t raceos-factory .
#   docker run -it --rm \
#     -v $(pwd):/workspace \
#     -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
#     raceos-factory
#
# For CI/CD:
#   docker run --rm \
#     -v $(pwd):/workspace \
#     -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
#     raceos-factory feature "implement X" --domain firmware --auto-approve
# ============================================================

# --- Stage 1: Build ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir hatchling

# Copy source
COPY pyproject.toml README.md CHANGELOG.md LICENSE ./
COPY src/ src/
COPY config/ config/
COPY specs/ specs/
COPY langgraph/ langgraph/

# Build wheel
RUN python -m hatchling build -t wheel

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

# Install Node.js (for MCP servers via npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm git \
    && rm -rf /var/lib/apt/lists/*

# Install the package from wheel
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy config (not baked into package — mounted or copied)
COPY config/ /app/config/
COPY specs/ /app/specs/
COPY langgraph/ /app/langgraph/

WORKDIR /workspace

# Default: interactive shell
ENTRYPOINT ["raceos"]
CMD []

# Labels
LABEL org.opencontainers.image.title="RaceOS AI Software Factory"
LABEL org.opencontainers.image.description="AI-native software factory for motorsport embedded development"
LABEL org.opencontainers.image.source="https://github.com/raceos/raceos-factory"
LABEL org.opencontainers.image.version="1.0.0"
