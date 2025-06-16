# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# If your app is in app/ directory
# COPY ./hackathon-service-account-key.json /app/hackathon-service-account-key.json
# RUN chmod 600 /app/hackathon-service-account-key.json

# Expose port
EXPOSE 8080

# Adjust this based on your actual file structure
# If app is in app/app.py, use app.app:app
# If app is in app/app.py, use app.app:app  
# If app is in root as app.py, use app:app
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app.app:app