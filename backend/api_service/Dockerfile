
FROM python:3.11-slim

WORKDIR /app
COPY backend /app/backend

RUN pip install --no-cache-dir -r /app/backend/api_service/requirements.txt

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "backend.api_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
