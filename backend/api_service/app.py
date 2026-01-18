
import os
import uuid
from typing import Optional, Any, Dict, List

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl
from google.cloud import pubsub_v1

from backend.api_service.auth import verify_bearer_token
from backend.shared.firestore_repo import create_job, update_job, job_ref, server_ts
from backend.shared.gcs import sign_download_url

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
TOPIC_ID = os.environ["PUBSUB_TOPIC_ID"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
SIGNED_URL_TTL_SECONDS = int(os.environ.get("SIGNED_URL_TTL_SECONDS", "900"))

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

app = FastAPI(title="Downloader API (Auth + Pub/Sub + Firestore)")

class AudioJobRequest(BaseModel):
    url: HttpUrl
    audio_format: str = "mp3"
    bitrate: str = "192"
    allow_playlist: bool = True
    playlist_items: Optional[str] = None
    cookie_file: Optional[str] = None

class VideoJobRequest(BaseModel):
    url: HttpUrl
    container: str = "mp4"
    max_height: Optional[int] = 1080
    prefer_codec: Optional[str] = None
    allow_playlist: bool = True
    playlist_items: Optional[str] = None
    cookie_file: Optional[str] = None

def require_uid(authorization: Optional[str]) -> str:
    try:
        return verify_bearer_token(authorization or "")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

def publish_job(job_id: str):
    # Message payload is job_id; worker reads options from Firestore.
    publisher.publish(topic_path, job_id.encode("utf-8")).result(timeout=10)

@app.post("/jobs/audio")
def create_audio(req: AudioJobRequest, authorization: Optional[str] = Header(None)):
    uid = require_uid(authorization)
    job_id = uuid.uuid4().hex
    create_job(job_id, {
        "id": job_id,
        "userId": uid,
        "kind": "audio",
        "status": "queued",
        "createdAt": server_ts(),
        "startedAt": None,
        "finishedAt": None,
        "error": None,
        "progress": None,
        "output": None,
        "options": req.model_dump(),
    })
    publish_job(job_id)
    return {"job_id": job_id}

@app.post("/jobs/video")
def create_video(req: VideoJobRequest, authorization: Optional[str] = Header(None)):
    uid = require_uid(authorization)
    job_id = uuid.uuid4().hex
    create_job(job_id, {
        "id": job_id,
        "userId": uid,
        "kind": "video",
        "status": "queued",
        "createdAt": server_ts(),
        "startedAt": None,
        "finishedAt": None,
        "error": None,
        "progress": None,
        "output": None,
        "options": req.model_dump(),
    })
    publish_job(job_id)
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: Optional[str] = Header(None)):
    uid = require_uid(authorization)
    snap = job_ref(job_id).get()
    if not snap.exists:
        raise HTTPException(404, "Job not found")
    job = snap.to_dict()
    if job.get("userId") != uid:
        raise HTTPException(403, "Forbidden")
    return job

@app.get("/jobs/{job_id}/download-url")
def get_download_url(job_id: str, authorization: Optional[str] = Header(None)):
    uid = require_uid(authorization)
    snap = job_ref(job_id).get()
    if not snap.exists:
        raise HTTPException(404, "Job not found")
    job = snap.to_dict()
    if job.get("userId") != uid:
        raise HTTPException(403, "Forbidden")

    out = job.get("output") or {}
    obj = out.get("object")
    bucket = out.get("bucket") or OUTPUT_BUCKET
    if not obj:
        raise HTTPException(409, "Job has no output yet")

    url = sign_download_url(bucket, obj, ttl_seconds=SIGNED_URL_TTL_SECONDS)
    return {"url": url, "expires_in": SIGNED_URL_TTL_SECONDS}
