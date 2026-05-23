FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY examples ./examples
COPY docs ./docs

CMD ["flow-memory", "run", "Explore the environment and report findings"]
