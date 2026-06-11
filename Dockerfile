# Dockerfile
FROM python:3.10-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Permette a Python di trovare sia app/ che src/
ENV PYTHONPATH=/workspace