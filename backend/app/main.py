from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import register_error_handlers
from app.routers import auth

app = FastAPI(title="같이 API")
register_error_handlers(app)
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """서버만 확인한다. 발표 전에 Render를 깨울 때 쓴다."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    """DB 연결까지 확인한다."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
