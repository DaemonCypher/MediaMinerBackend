
import time
from typing import Any, Dict
from google.cloud import firestore

db = firestore.Client()

def server_ts():
    return firestore.SERVER_TIMESTAMP

def job_ref(job_id: str):
    return db.collection("jobs").document(job_id)

def event_ref(job_id: str):
    return job_ref(job_id).collection("events")

def create_job(job_id: str, doc: Dict[str, Any]):
    job_ref(job_id).set(doc)

def update_job(job_id: str, patch: Dict[str, Any]):
    job_ref(job_id).update(patch)

def add_event(job_id: str, event: Dict[str, Any]):
    event_ref(job_id).add(event)

class ProgressThrottler:
    def __init__(self, min_interval_sec: float = 1.0):
        self.min_interval_sec = min_interval_sec
        self._last: Dict[str, float] = {}

    def should_write(self, job_id: str) -> bool:
        now = time.time()
        last = self._last.get(job_id, 0.0)
        if now - last >= self.min_interval_sec:
            self._last[job_id] = now
            return True
        return False
