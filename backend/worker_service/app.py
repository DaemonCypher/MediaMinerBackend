
import base64
import glob
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException

from backend.shared.downloader import download_audio, download_video, DOWNLOAD_DIR
from backend.shared.gcs import upload_file
from backend.shared.firestore_repo import (
    job_ref, update_job, add_event, server_ts, ProgressThrottler
)

OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
progress_throttle = ProgressThrottler(min_interval_sec=float(os.environ.get("PROGRESS_MIN_INTERVAL_SEC", "1.0")))

app = FastAPI(title="Downloader Worker (Pub/Sub push)")

def find_newest(patterns) -> Optional[str]:
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))

def push_progress(job_id: str, d: Dict[str, Any]):
    ev = {
        "type": "progress",
        "status": d.get("status"),
        "percent": (d.get("_percent_str") or "").strip(),
        "speed": (d.get("_speed_str") or "").strip(),
        "eta": (d.get("_eta_str") or "").strip(),
        "filename": d.get("filename"),
        "at": server_ts(),
    }

    add_event(job_id, ev)

    if progress_throttle.should_write(job_id):
        update_job(job_id, {
            "progress": {
                "status": ev["status"],
                "percent": ev["percent"],
                "speed": ev["speed"],
                "eta": ev["eta"],
                "filename": ev["filename"],
            }
        })

@app.post("/pubsub")
async def pubsub_handler(req: Request):
    """Pub/Sub push handler.

    Expected payload:
    {
      "message": {"data":"base64(job_id)", ...},
      "subscription":"..."
    }
    """
    body = await req.json()
    msg = body.get("message", {})
    data_b64 = msg.get("data")
    if not data_b64:
        raise HTTPException(400, "Missing message.data")

    job_id = base64.b64decode(data_b64).decode("utf-8").strip()

    snap = job_ref(job_id).get()
    if not snap.exists:
        # Acknowledge to avoid infinite retries for missing jobs
        return {"ok": True, "ignored": "job_not_found"}

    job = snap.to_dict()
    kind = job.get("kind")
    options = job.get("options") or {}

    update_job(job_id, {"status": "running", "startedAt": server_ts()})
    add_event(job_id, {"type": "status", "status": "running", "at": server_ts()})

    try:
        if kind == "audio":
            download_audio(
                url=str(options["url"]),
                audio_format=options.get("audio_format", "mp3"),
                bitrate=options.get("bitrate", "192"),
                allow_playlist=options.get("allow_playlist", True),
                playlist_items=options.get("playlist_items"),
                cookie_file=options.get("cookie_file"),
                on_progress=lambda d: push_progress(job_id, d),
            )

            out_file = find_newest([
                os.path.join(DOWNLOAD_DIR, "*.mp3"),
                os.path.join(DOWNLOAD_DIR, "*.m4a"),
                os.path.join(DOWNLOAD_DIR, "*.opus"),
                os.path.join(DOWNLOAD_DIR, "*.flac"),
                os.path.join(DOWNLOAD_DIR, "*.wav"),
            ])

        elif kind == "video":
            download_video(
                url=str(options["url"]),
                container=options.get("container", "mp4"),
                max_height=options.get("max_height"),
                prefer_codec=options.get("prefer_codec"),
                allow_playlist=options.get("allow_playlist", True),
                playlist_items=options.get("playlist_items"),
                cookie_file=options.get("cookie_file"),
                on_progress=lambda d: push_progress(job_id, d),
            )

            out_file = find_newest([
                os.path.join(DOWNLOAD_DIR, "*.mp4"),
                os.path.join(DOWNLOAD_DIR, "*.mkv"),
                os.path.join(DOWNLOAD_DIR, "*.webm"),
            ])
        else:
            raise ValueError(f"Unknown job kind: {kind}")

        if not out_file or not os.path.isfile(out_file):
            raise RuntimeError("Download finished but output file not found")

        object_name = f"outputs/{job_id}/{os.path.basename(out_file)}"
        gcs_object, size_bytes = upload_file(OUTPUT_BUCKET, out_file, object_name)

        update_job(job_id, {
            "status": "finished",
            "finishedAt": server_ts(),
            "output": {
                "bucket": OUTPUT_BUCKET,
                "object": gcs_object,
                "sizeBytes": size_bytes,
            }
        })
        add_event(job_id, {"type": "status", "status": "finished", "at": server_ts()})
        return {"ok": True}

    except Exception as e:
        update_job(job_id, {
            "status": "error",
            "error": str(e),
            "finishedAt": server_ts(),
        })
        add_event(job_id, {"type": "error", "message": str(e), "at": server_ts()})
        raise HTTPException(500, str(e))
