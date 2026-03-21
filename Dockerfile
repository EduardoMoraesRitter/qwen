FROM python:3.11-slim

# Deps do sistema pra compilar llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar deps Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar app
COPY main.py .
COPY static/ static/

# Criar pasta de sessions
RUN mkdir -p sessions models

# Copiar modelo GGUF para dentro da imagem (necessario para Cloud Run)
COPY models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf models/

ENV PORT=8080
ENV N_THREADS=4
EXPOSE 8080

CMD ["python", "main.py"]
