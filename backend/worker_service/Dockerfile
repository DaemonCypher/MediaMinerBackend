
FROM python:3.11-slim

# ffmpeg is required for merging video+audio and for audio extraction.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend /app/backend

RUN pip install --no-cache-dir -r /app/backend/worker_service/requirements.txt

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "backend.worker_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
