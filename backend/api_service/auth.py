
import firebase_admin
from firebase_admin import auth as fb_auth, credentials

# Cloud Run: use Application Default Credentials (service account) by default.
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.ApplicationDefault())

def verify_bearer_token(auth_header: str) -> str:
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Missing Bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    decoded = fb_auth.verify_id_token(token)
    return decoded["uid"]
