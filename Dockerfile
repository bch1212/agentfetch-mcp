FROM python:3.11-slim

WORKDIR /app

# Install system deps for trafilatura's optional html5-parser etc.
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt-dev \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY agentfetch ./agentfetch

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

# AgentFetch's MCP server speaks stdio — Glama / Claude Desktop attach via the entrypoint.
ENTRYPOINT ["python", "-m", "agentfetch.mcp.server"]
