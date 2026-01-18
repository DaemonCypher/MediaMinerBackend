
# Backend: GCP Cloud Run + Pub/Sub + Firestore (with Firebase Auth)

This backend is split into two Cloud Run services:

- **API Service**: authenticated endpoints to create jobs, list jobs, and generate signed download URLs
- **Worker Service**: Pub/Sub push endpoint to execute jobs with yt-dlp + ffmpeg and write progress/events to Firestore

## Architecture
1. Client signs in with Firebase Auth and sends `Authorization: Bearer <ID_TOKEN>` to API.
2. API verifies token, creates `jobs/{jobId}` in Firestore, publishes jobId to Pub/Sub.
3. Pub/Sub pushes message to Worker `/pubsub`.
4. Worker runs yt-dlp, updates Firestore job doc + appends events, uploads output to GCS.
5. Client watches Firestore `jobs/{jobId}` (realtime). For download, call API to get signed URL.

## Services
- `backend/api_service`
- `backend/worker_service`
- `backend/shared`

## Required GCP resources
- Firestore (Native mode)
- Pub/Sub topic (e.g. `download-jobs`)
- Pub/Sub push subscription to Worker `/pubsub`
- Cloud Storage bucket for outputs

## Environment Variables
### API service
- `GCP_PROJECT_ID`
- `PUBSUB_TOPIC_ID`
- `OUTPUT_BUCKET` (same bucket as worker; used for signed URLs)
- `SIGNED_URL_TTL_SECONDS` (optional, default 900)

### Worker service
- `OUTPUT_BUCKET`
- `DOWNLOAD_DIR` (optional, default `/tmp/downloads`)
- `FFMPEG_PATH` (optional; if not set relies on ffmpeg in PATH)

## IAM (service accounts)
### API service account needs:
- Pub/Sub Publisher (topic publish)
- Firestore access (read/write jobs)
- Storage Object Viewer (or Admin) for signed URLs (plus signing permissions)

### Worker service account needs:
- Pub/Sub push invoker (handled by Cloud Run Invoker binding on worker)
- Firestore access (read/write jobs & events)
- Storage Object Admin (upload outputs)

## Local dev
These services are intended for Cloud Run, but you can run locally with ADC:
- `gcloud auth application-default login`
- set env vars and run uvicorn

## Note about ffmpeg on Cloud Run
Install ffmpeg in your worker container (recommended) or provide `FFMPEG_PATH`.
