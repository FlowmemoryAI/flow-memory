FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
ARG FLOW_MEMORY_EXTRAS=""

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN if [ -n "$FLOW_MEMORY_EXTRAS" ]; then pip install --no-cache-dir -e ".[${FLOW_MEMORY_EXTRAS}]"; else pip install --no-cache-dir -e .; fi
COPY examples ./examples
COPY docs ./docs
COPY scripts ./scripts
EXPOSE 8765

CMD ["flow-memory", "run", "Explore the environment and report findings"]
