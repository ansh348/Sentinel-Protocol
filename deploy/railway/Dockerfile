# Phase-1c Railway B2 image  --  PREPARED / UNTESTED (FEASIBILITY, NOT FROZEN)
# Could not be built here: the Docker daemon is down (Docker Desktop not started).
# Build after starting Docker:  docker build --build-arg CLAUDE_CLI_VERSION=2.1.177 -t tw-b2 -f deploy/railway/Dockerfile .
#
# B2 = the REAL Claude Code CLI authenticated with ANTHROPIC_API_KEY (request-equivalent
# path proven last task). NOT the thin-API D38 path.
#
# CLI PIN: 2.1.177 -- the version Phase-1b ACTUALLY ran on (runtime stamp in all 172
# matrix_1b trace cells: payload.cli_version == "2.1.177"; run_one.py:940 + queue.py
# cli_version_guard). prereg.md DECLARED 2.1.170 but the CLI auto-updated to 2.1.177
# before the matrix executed -- the declared pin is stale; the runtime stamp is the truth.
# (3-way capture: 2.1.177 worker catalog == 2.1.170 (31 tools); compile differs from both
# 170 and 193. See runs/matrix_1c/cli_version_diff.json.) npm has 2.1.177 (download-on-install).
FROM node:22-bookworm-slim

ARG CLAUDE_CLI_VERSION=2.1.177
ENV CLAUDE_CLI_VERSION=${CLAUDE_CLI_VERSION}

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*

# pin + VERIFY the CLI version (drift would silently change the request shape -> break equivalence)
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CLI_VERSION} \
    && INSTALLED="$(claude --version | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')" \
    && echo "installed claude CLI: $INSTALLED (pinned ${CLAUDE_CLI_VERSION})" \
    && [ "$INSTALLED" = "${CLAUDE_CLI_VERSION}" ] || (echo "FATAL: CLI version mismatch ($INSTALLED != ${CLAUDE_CLI_VERSION})" && exit 1)

WORKDIR /app
COPY . /app
# Install the FULL runtime dependency set from requirements.txt (httpx + PyYAML are
# load-bearing for the conductor side-channel client + task loading; the prior hardcoded
# `fastapi uvicorn psutil` list dropped them -> ModuleNotFoundError at run).
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt || \
    pip3 install --no-cache-dir -r requirements.txt

# ANTHROPIC_API_KEY is injected as a Railway SERVICE VARIABLE at runtime (never baked in).
# /data is the attached persistent volume (see railway.toml + dashboard steps).
ENTRYPOINT ["bash", "deploy/railway/entrypoint.sh"]
