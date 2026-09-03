FROM python:3.12-slim

# GDAL runtime libraries for rasterio wheels + build essentials for psycopg2 fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libexpat1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV EARTHYY_STORAGE_ROOT=/data/storage
RUN mkdir -p /data/storage

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
