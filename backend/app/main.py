from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .config import FRONTEND_ORIGINS
from .database import Base, SessionLocal, engine
from .models import ContactMessage
from .schemas import ContactCreate, ContactCreated


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
