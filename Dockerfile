FROM python:3.12-slim

# Install system deps (if you hit issues later, we can add more here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure both project root and backend module are discoverable
ENV PYTHONPATH=/app:/app/backend

# Copy requirements first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI app code
COPY . /app

# Generate Prisma client
RUN prisma generate --schema=/app/backend/schema.prisma

# Expose FastAPI port
EXPOSE 8000

# Use uvicorn to run the FastAPI app located in backend/main.py
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
