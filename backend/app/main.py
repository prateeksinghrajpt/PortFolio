import base64
import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from fastapi import Depends, Header, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .config import ADMIN_EMAIL, ADMIN_TOKEN_SECRET, FRONTEND_ORIGINS, GOOGLE_CLIENT_ID
from .database import Base, SessionLocal, engine
from .models import ContactMessage
from .schemas import AdminLogin, AdminMessage, AdminToken, ContactCreate, ContactCreated


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for this small portfolio starter. Use Alembic migrations for larger apps.
    if engine is not None:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Prateek Portfolio API",
    description="Contact endpoint for the AI and backend engineering portfolio.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def get_db():
    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Contact storage is not configured yet. Please try again later.",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _encode_admin_token(email: str) -> str:
    if not ADMIN_TOKEN_SECRET:
        raise HTTPException(status_code=503, detail="Admin login is not configured yet.")
    payload = json.dumps({"email": email, "exp": int(time.time()) + 60 * 60 * 12}, separators=(",", ":")).encode()
    signature = hmac.new(ADMIN_TOKEN_SECRET.encode(), payload, hashlib.sha256).digest()
    return f"{base64.urlsafe_b64encode(payload).decode().rstrip('=')}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def _decode_admin_token(authorization: str | None = Header(default=None)) -> str:
    if not ADMIN_TOKEN_SECRET or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication is required.")
    try:
        encoded_payload, encoded_signature = authorization.removeprefix("Bearer ").split(".", 1)
        padding = "=" * (-len(encoded_payload) % 4)
        payload = base64.urlsafe_b64decode(encoded_payload + padding)
        expected = hmac.new(ADMIN_TOKEN_SECRET.encode(), payload, hashlib.sha256).digest()
        signature_padding = "=" * (-len(encoded_signature) % 4)
        signature = base64.urlsafe_b64decode(encoded_signature + signature_padding)
        data = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid admin session.")
    if not hmac.compare_digest(signature, expected) or data.get("exp", 0) < time.time() or data.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Admin session has expired.")
    return data["email"]


@app.get("/")
def root():
    return {"service": "Prateek Portfolio API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "database_configured": engine is not None}


@app.post("/api/contact", response_model=ContactCreated, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    contact = ContactMessage(name=payload.name, email=str(payload.email), message=payload.message)
    try:
        db.add(contact)
        db.commit()
        db.refresh(contact)
    except Exception as exc:
        db.rollback()
        # Do not leak database details to the public client.
        raise HTTPException(status_code=503, detail="Unable to save your message right now.") from exc
    return ContactCreated(id=contact.id, message="Your message was received.")


@app.post("/api/admin/login", response_model=AdminToken)
def admin_login(payload: AdminLogin):
    if not GOOGLE_CLIENT_ID or not ADMIN_TOKEN_SECRET:
        raise HTTPException(status_code=503, detail="Admin login is not configured yet.")
    try:
        identity = id_token.verify_oauth2_token(payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified.") from exc
    email = str(identity.get("email", "")).lower()
    if not identity.get("email_verified") or email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="This Google account is not authorized for admin access.")
    return AdminToken(token=_encode_admin_token(email))


@app.get("/api/admin/messages", response_model=list[AdminMessage])
def admin_messages(_: str = Depends(_decode_admin_token), db: Session = Depends(get_db)):
    return db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).all()
