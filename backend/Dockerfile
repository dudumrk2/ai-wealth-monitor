# Use a lightweight Python base image
FROM python:3.11-slim

# Set the working directory to /app
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source code to /app
COPY . .

# Expose port 8080
EXPOSE 8080

# Set the startup command.
# Cloud Run injects the port via the $PORT environment variable.
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
