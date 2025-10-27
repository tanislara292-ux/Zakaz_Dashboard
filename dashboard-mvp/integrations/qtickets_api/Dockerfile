# Production Dockerfile for QTickets API integration
# Multi-stage build for minimal final image

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r etl && useradd -r -g etl etl
RUN chown -R etl:etl /app
USER etl

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; import os; print('OK')" || exit 1

# Set entrypoint
ENTRYPOINT ["python", "-m", "integrations.qtickets_api.loader"]

# Default arguments (can be overridden)
CMD ["--envfile", "/run/secrets/.env.qtickets_api", "--since-hours", "24"]

# Development stage (optional)
FROM base as development

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-cov black flake8

# Copy test files
COPY tests/ ./tests/
COPY fixtures/ ./fixtures/

# Override entrypoint for development
ENTRYPOINT ["python", "-m", "pytest"]
