# Dockerfile
FROM python:3.11-slim

WORKDIR /workspace

COPY requirements.txt .

# Installiamo prima torch e torchvision in versione CPU-only per evitare i binari CUDA (risparmiando oltre 2GB di spazio)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Permette a Python di trovare sia app/ che src/
ENV PYTHONPATH=/workspace