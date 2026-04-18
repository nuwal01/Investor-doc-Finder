"""
auth_middleware.py — Firebase Admin SDK: token verification + Firestore client.

Usage:
    from auth_middleware import verify_token, db, save_search_to_firestore

    user = await verify_token(request)   # raises HTTP 401 on failure
    uid  = user["uid"]

Firestore Security Rules (paste in Firebase Console → Firestore → Rules):

    rules_version = '2';
    service cloud.firestore {
      match /databases/{database}/documents {
        match /users/{uid}/searches/{searchId} {
          allow read, write: if request.auth != null
                             && request.auth.uid == uid;
        }
      }
    }
"""

import os

import firebase_admin
from firebase_admin import auth, credentials, firestore
from fastapi import HTTPException, Request

# ── Initialize Firebase Admin (once per process) ──────────────────────────────

_initialized = False
db = None          # Firestore client, set during _init_firebase()


def _init_firebase() -> None:
    global _initialized, db
    if _initialized:
        return
    service_account_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json"
    )
    if not os.path.exists(service_account_path):
        print(
            f"[auth_middleware] WARNING: Firebase service account not found at "
            f"'{service_account_path}'. Auth will return 503 until the file is added."
        )
        _initialized = True   # mark as attempted so we don't retry on every request
        return
    try:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[auth_middleware] Firebase Admin initialized successfully.")
    except Exception as e:
        print(f"[auth_middleware] Firebase init error: {e}")
    _initialized = True


_init_firebase()

# ── Token verification ────────────────────────────────────────────────────────


async def verify_token(request: Request) -> dict:
    """
    Extract and verify the Firebase ID token from the Authorization header.

    Returns the decoded token dict (contains uid, email, etc.).
    Raises HTTP 401 if the token is missing, malformed, or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
        )

    token = auth_header[len("Bearer "):]
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    if not _initialized or db is None:
        # Firebase not yet configured — service account JSON is missing
        raise HTTPException(
            status_code=503,
            detail="Firebase not configured on server. Add firebase-service-account.json to backend/.",
        )

    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except auth.InvalidIdTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")


# ── Firestore save helper ─────────────────────────────────────────────────────


def save_search_to_firestore(uid: str, result: dict) -> str | None:
    """
    Save an enriched search result to users/{uid}/searches/.

    Called from agent.py after a successful result is found.
    result should include: url, source, confidence, score,
    company_name, normalized_name, doc_type, year, raw_query,
    country, exchange_mic.

    Returns the new document ID or None on failure (errors are swallowed
    so they never interrupt the main search flow).
    """
    if db is None:
        return None
    try:
        ref = db.collection("users").document(uid).collection("searches")
        ts, doc_ref = ref.add({
            **result,
            "fetched_at": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id
    except Exception as e:
        print(f"[auth_middleware] Firestore save error: {e}")
        return None
