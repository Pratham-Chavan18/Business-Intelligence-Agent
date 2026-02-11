FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Expose port
EXPOSE 8000

# Run from backend directory
WORKDIR /app/backend
CMD ["python", "main.py"]
