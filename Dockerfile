FROM python:3.12-slim AS frontend-builder

# Install Node.js (matches README minimum: 18.x)
ENV NODE_VERSION=20.11.1
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION%.*}.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/frontend
COPY frontend/package*.json* ./
RUN npm ci --only=production
COPY frontend/ .
RUN npm run build

# ---------------------------------------------------------------------------
# Backend stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# System libraries required by geopandas, rasterio, shapely.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev libproj-dev libgeos-dev proj-data proj-bin \
        gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source.
COPY . .

# Copy pre-built frontend assets.
COPY --from=frontend-builder /app/frontend/dist/ /app/frontend/dist/

# Expose the uvicorn port.
EXPOSE 8000

# Run the pipeline once on container start, then serve.
# HACKATHON NOTE: --reload is omitted in production; data is regenerated
# by re-running the pipeline separately or via GET /reload.
CMD python pipeline.py && uvicorn main:app --host 0.0.0.0 --port 8000
