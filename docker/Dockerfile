FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY schemas ./schemas
COPY policies ./policies
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "flow_memory", "--json", "Explore and report"]
