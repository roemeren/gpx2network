# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install system dependencies: osmium + GDAL
RUN apt-get update && apt-get install -y osmium-tool gdal-bin

# Copy the rest of the source
COPY . .

# Expose Dash port (Render overrides $PORT)
EXPOSE 8050

# Start Dash via Gunicorn using Render's dynamic port
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:$PORT"]
