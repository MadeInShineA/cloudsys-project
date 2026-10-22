# Syntax=docker/dockerfile:1

# Stage 1: Build Stage
FROM --platform=$BUILDPLATFORM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install system dependencies for HDF5
RUN apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies in a virtual environment
COPY requirements.txt .
RUN python -m venv venv && \
    . venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Stage 2: Runtime Stage
FROM --platform=$BUILDPLATFORM python:3.11-slim-bookworm

WORKDIR /app


# Copy the application and virtual environment from the builder stage
COPY --from=builder /app /app

# Set environment variables to use the virtual environment
ENV PATH="/app/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Set the command to start your application
CMD ["python", "/app/controller.py"]
