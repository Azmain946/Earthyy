FROM python:3.12-slim

# GDAL headers are required on Apple Silicon (aarch64) where rasterio
# may compile from source instead of using a prebuilt wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    curl \
    libexpat1 \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_CONFIG=/usr/bin/gdal-config \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV EARTHYY_STORAGE_ROOT=/data/storage
RUN mkdir -p /data/storage

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
