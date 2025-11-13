# Multi-stage build for Entmoot backend
# Stage 1: Build stage
FROM python:3.10-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production stage
FROM python:3.10-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal36 \
    libproj25 \
    libgeos-c1t64 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the application in editable mode
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /app/data/uploads/logs /app/data/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENTMOOT_UPLOADS_DIR=/app/data/uploads
ENV ENTMOOT_ENVIRONMENT=production
ENV ENTMOOT_CORS_ORIGINS=*

# Expose port
EXPOSE 8000

# Run the application
# Use shell form to allow environment variable substitution
CMD uvicorn entmoot.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
