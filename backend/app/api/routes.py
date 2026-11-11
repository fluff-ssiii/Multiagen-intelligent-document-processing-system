from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import document_routes, review_routes
from app.database.connection import get_db

api_router = APIRouter(prefix="/api")
api_router.include_router(document_routes.router)
api_router.include_router(review_routes.router)


@api_router.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "database": db_status}