FROM python:3.11-slim

WORKDIR /ast-platform

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps (exclude MetaTrader5 — Windows only)
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic pandas numpy python-multipart httpx

# App source
COPY app/       ./app/
COPY frontend/  ./frontend/
COPY run.py     .

# Create data dirs
RUN mkdir -p logs data

EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
