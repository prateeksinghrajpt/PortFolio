import os
from dotenv import load_dotenv

load_dotenv()


def get_origins() -> list[str]:
    raw = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
FRONTEND_ORIGINS = get_origins()
