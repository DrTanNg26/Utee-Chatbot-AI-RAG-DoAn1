"""
main.py - Diem khoi chay chinh cua Backend FastAPI Chatbot AI UTee (Do an 1 - UTT).
Ke thua cau truc app/main.py cua repo NCKH, tu dong khoi tao CSDL + nạp Pure FAISS Index khi startup.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.auth import routers as auth_routers
from app.auth.util import get_optional_user
from app.config.cors import app
from app.config.database import Base, engine, get_db
from app.config_manager import load_config
import app.models as models
import app.routes as admin_routes
import app.services.admin_service as admin_service
import app.services.chat_service as chat_service
from app.services.student_service import student_router
from app.vectorstore import VectorStore


@asynccontextmanager
async def lifespan(fastapi_app):
    # 1. Dam bao cac bang CSDL da duoc tao
    Base.metadata.create_all(bind=engine)
    # 2. Load Pure FAISS VectorStore 1 lan vao RAM khi server khoi dong (ke thua NCKH)
    vs = VectorStore.get_instance()
    print(f"[STARTUP] UTee Backend sẵn sàng! Pure FAISS đang giữ {vs.index.ntotal:,} vectors.")
    yield


app.router.lifespan_context = lifespan

# Dang ky day du cac Router (Ho tro song song chuan NCKH va chuan RESTful /api/v1/*)
app.include_router(auth_routers.router)
app.include_router(auth_routers.v1_auth_router)
app.include_router(chat_service.v1_chat_router)
app.include_router(student_router)
app.include_router(admin_routes.admin_router)
app.include_router(admin_routes.v1_admin_router)


@app.get("/", tags=["Health & System"])
def root():
    cfg = load_config()
    vs = VectorStore.get_instance()
    return {
        "service": "UTee AI Companion Backend",
        "version": "1.0.0",
        "status": "online",
        "botName": cfg.get("botName", "UTee AI Companion"),
        "welcomeMessage": cfg.get("welcomeMessage", ""),
        "faissVectors": vs.index.ntotal,
        "docsUrl": "/docs",
    }


@app.get("/health", tags=["Health & System"])
@app.get("/api/v1/health", tags=["Health & System"])
def health_check(db: Session = Depends(get_db)):
    vs = VectorStore.get_instance()
    user_count = db.query(models.User).count()
    doc_count = db.query(models.Document).count()
    return {
        "EC": 0,
        "EM": "Healthy",
        "DT": {
            "database": "connected",
            "usersCount": user_count,
            "documentsCount": doc_count,
            "faissVectorsCount": vs.index.ntotal,
            "embeddingModel": vs.embedding_model,
            "geminiKeysLoaded": len(vs.clients),
        },
    }


# ================= Endpoints Ke thua Truc tiep Repo NCKH =================


@app.post("/chat", tags=["Chat (NCKH Compatible)"])
async def chat_nckh(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    try:
        return await chat_service.chat_legacy_nckh(request=request, db=db, current_user=current_user)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/ck", tags=["Chat (NCKH Compatible)"])
def assign_cookie_nckh(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    return chat_service.assign_cookie(response=response, request=request, db=db)


@app.get("/documents/{doc_id}/signed", tags=["Documents Viewer"])
@app.get("/api/v1/documents/{doc_id}/signed", tags=["Documents Viewer"])
def view_doc_signed(
    doc_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    return admin_service.serve_signed_document(doc_id=doc_id, token=token, db=db)


@app.get("/api/v1/documents/{doc_id}/view-link", tags=["Documents Viewer"])
def get_public_citation_view_link(doc_id: int, db: Session = Depends(get_db)):
    """Cho phep sinh vien click vao huy hieu nguon trich dan RAG de mo xem van ban quy che goc."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id, models.Document.is_active.is_(True)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu nguồn trích dẫn.")
    url = admin_service.create_signed_url(doc_id, expires_in=1800)
    return {"EC": 0, "EM": "Success", "DT": {"url": url, "title": doc.title, "name": doc.name}}
