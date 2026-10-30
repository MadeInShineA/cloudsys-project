# Syntax=docker/dockerfile:1

# Bibliothèque standard uniquement (sqlite3, json) : pas de venv ni de requirements
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY analyser.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/analyser.py"]
