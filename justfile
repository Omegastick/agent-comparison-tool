# Rebuild the Docker image
rebuild:
    docker rmi -f agent-benchmark-opencode 2>/dev/null || true
    docker build -t agent-benchmark-opencode docker/
