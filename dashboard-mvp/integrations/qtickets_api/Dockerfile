# Production Dockerfile for QTickets API integration
# Single-stage build for production deployment

FROM python:3.11-slim

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
COPY integrations/qtickets_api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user but allow reading secrets
# Note: Running as root is acceptable for production in this case
# to avoid permission issues with mounted secrets
RUN groupadd -r etl && useradd -r -g etl etl
RUN chown -R etl:etl /app

# Set entrypoint
ENTRYPOINT ["python", "-m", "integrations.qtickets_api.loader"]

# Default arguments (can be overridden)
CMD ["--since-hours", "4"]
