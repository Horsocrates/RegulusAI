FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck + uv
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY regulus ./regulus

# Install dependencies
RUN uv sync --frozen

# Create data directory
RUN mkdir -p /app/data/cache

# Expose port
EXPOSE 8000

# Run server
CMD ["uv", "run", "uvicorn", "regulus.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
