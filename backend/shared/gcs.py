
import os
from typing import Tuple, Optional
from google.cloud import storage

client = storage.Client()

def upload_file(bucket_name: str, local_path: str, object_name: str) -> Tuple[str, int]:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.upload_from_filename(local_path)
    return object_name, os.path.getsize(local_path)

def sign_download_url(bucket_name: str, object_name: str, ttl_seconds: int = 900) -> str:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(expiration=ttl_seconds, method="GET")
