FROM node:20-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode globally
RUN npm install -g opencode-ai

# Working directory for repo
WORKDIR /workspace

# Copy entrypoint scripts
COPY entrypoint.sh /entrypoint.sh
COPY analyze-entrypoint.sh /analyze-entrypoint.sh
RUN chmod +x /entrypoint.sh /analyze-entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
