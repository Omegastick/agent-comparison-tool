FROM node:24-bookworm-slim

# Pi runtime deps: bash (entrypoint), git (clone/diff), ripgrep (Pi's search).
RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Pin Pi for reproducibility; --ignore-scripts avoids running untrusted
# postinstall hooks at build time.
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.80.2

WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
COPY extract-output.mjs /extract-output.mjs
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
