# Multi-stage build for React frontend + FastAPI backend

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Remove .env files to prevent localhost URLs in production build
RUN rm -f .env .env.local .env.development .env.production

# Build with empty API URL for production (uses relative URLs)
RUN npm run build

# Stage 2: Python backend with frontend static files
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app

# Copy built frontend from previous stage
COPY --from=frontend-build /frontend/dist ./static

# Update main.py to serve static files (we'll modify the app to do this)
# For now, we'll use a startup script

# Expose port
ENV PORT=8080
EXPOSE 8080

# Run the application
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
