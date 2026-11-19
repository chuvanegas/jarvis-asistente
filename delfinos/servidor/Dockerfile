# Servidor de compilación de DelfínOS (ufbt + FastAPI)
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential libusb-1.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ufbt

# Descarga el SDK del Flipper una vez (la primera compilación si no, lo baja sola)
RUN ufbt update || true

COPY app.py .
# COPY web ./web      # descomenta si sirves la web desde aquí

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
