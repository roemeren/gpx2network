# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install system dependencies for geoprocessing: osmium + GDAL
RUN apt-get update && apt-get install -y \
        osmium-tool \
        gdal-bin \
    && apt-get clean && rm -rf /var/lib/apt/lists/*  # clean up to reduce image size

# Copy the rest of the source code
COPY . .

# Expose Dash port (Render will override $PORT)
EXPOSE 8050

# Start Dash via Gunicorn
# - app.app:server refers to the Flask server inside app/app.py
# - bind to 0.0.0.0:$PORT so Render can dynamically assign the port
CMD gunicorn app:server --bind 0.0.0.0:$PORT
