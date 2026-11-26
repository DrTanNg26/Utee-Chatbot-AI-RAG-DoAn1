"""
admin_service.py - Quan tri Kho tri thuc RAG (Upload / Chunk / Gemini Embed / FAISS / Toggle / Delete),
Signed URL xem tai lieu goc va Thong ke Nhat ky Van hanh & Bao mat.
Ke thua truc tiep app/services/admin_service.py cua repo NCKH.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
import jwt
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.auth.security import record_operation_log
from app.config.database import SessionLocal
import app.models as models
from app.vectorstore import VectorStore, extract_pages_from_file, semantic_chunk_pages

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_RAW_DIR = BACKEND_DIR.parent / "RAG" / "data" / "raw"
UPLOAD_DATA_DIR = BACKEND_DIR / "app" / "data"

ALGORITHM = "HS256"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "utee_doan1_super_secret_jwt_key_change_in_production_2026")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    return f"{size_bytes / 1024**3:.1f} GB"


def stats_service(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Thong ke luot nguoi dung, tin nhan, tai lieu va canh bao bao mat theo ngay (ke thua NCKH)."""
    db = SessionLocal()
    try:
        date_filter = []
        if start_date:
            date_filter.append(func.date(models.Message.created_at) >= start_date)
        if end_date:
            date_filter.append(func.date(models.Message.created_at) <= end_date)

        users_query = (
            db.query(
                func.date(models.Message.created_at).label("date"),
                func.count(func.distinct(models.Message.user_id)).label("count"),
            )
            .group_by(func.date(models.Message.created_at))
            .order_by(func.date(models.Message.created_at))
        )
        if date_filter:
            users_query = users_query.filter(*date_filter)
        users_per_day = users_query.all()

        messages_query = (
            db.query(
                func.date(models.Message.created_at).label("date"),
                func.count().label("count"),
            )
            .group_by(func.date(models.Message.created_at))
            .order_by(func.date(models.Message.created_at))
        )
        if date_filter:
            messages_query = messages_query.filter(*date_filter)
        messages_per_day = messages_query.all()

        total_documents = db.query(models.Document).count()
        active_documents = db.query(models.Document).filter(models.Document.is_active.is_(True)).count()
        blocked_events = (
            db.query(models.OperationLog)
            .filter(
                models.OperationLog.event_type.in_(
                    ["AUTH_DENIED", "CROSS_ACCOUNT_DENIED", "PROMPT_INJECTION_BLOCKED"]
                )
            )
            .count()
        )

        recent_messages = (
            db.query(models.Message)
            .filter(models.Message.role == "user")
            .order_by(models.Message.created_at.desc())
            .limit(10)
            .all()
        )

        vs = VectorStore.get_instance()
        stats = {
            "users": [{"date": str(d.date), "count": d.count} for d in users_per_day],
            "messages": [{"date": str(d.date), "count": d.count} for d in messages_per_day],
            "documents": total_documents,
            "activeDocuments": active_documents,
            "totalFaissVectors": vs.index.ntotal,
            "blockedSecurityEvents": blocked_events,
            "dataMessagesWithDates": [
                {
                    "id": msg.id,
                    "user": str(msg.user_id) if msg.user_id else "guest",
                    "message": msg.message,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in recent_messages
            ],
        }
        return {"EM": "Get stats data success!", "EC": 0, "DT": stats}
    except Exception as exc:
        return {"EC": 1, "EM": f"Lỗi thống kê admin: {exc}", "DT": {}}
    finally:
        db.close()


def get_all_documents(db: Session) -> dict:
    docs = db.query(models.Document).order_by(desc(models.Document.upload_date), desc(models.Document.id)).all()
    return {
        "EC": 0,
        "EM": "Get document metadata successful!",
        "DT": [
            {
                "id": d.id,
                "name": d.name,
                "title": d.title,
                "category": d.category,
                "department": d.department,
                "effectiveDate": d.effective_date,
                "sourceUrl": d.source_url,
                "size": d.size,
                "uploadDate": d.upload_date.strftime("%Y-%m-%d") if d.upload_date else None,
                "status": d.status,
                "isActive": d.is_active,
                "chunkCount": d.chunk_count,
                "type": d.type,
            }
            for d in docs
        ],
    }


async def add_documents(
    files: List[UploadFile],
    db: Session,
    title: Optional[str] = None,
    category: str = "Tài liệu UTT",
    department: str = "Phòng Đào tạo UTT",
    effective_date: Optional[str] = None,
    source_url: Optional[str] = None,
    admin_user: Optional[models.User] = None,
) -> dict:
    """
    Upload file moi (PDF, DOCX, XLSX, TXT, MD) -> Luu file -> Trich xuat & Semantic Chunking
    -> Embed qua Google Gemini Studio API -> Them vao Pure FAISS -> Luu vector_ids vao Postgres!
    """
    UPLOAD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for file in files:
        safe_name = Path(file.filename or "uploaded_doc.pdf").name
        existing_doc = db.query(models.Document).filter(models.Document.name == safe_name).first()
        if existing_doc:
            return {
                "EC": 2,
                "EM": f"Đã tồn tại tài liệu '{safe_name}' trong hệ thống! Vui lòng xóa bản cũ trước khi tải lên lại.",
                "DT": [],
            }

        file_path = UPLOAD_DATA_DIR / safe_name
        raw_bytes = await file.read()
        file_path.write_bytes(raw_bytes)

        doc_title = (title or Path(safe_name).stem.replace("-", " ").replace("_", " ").title()).strip()
        ext_type = Path(safe_name).suffix.lstrip(".").upper() or "PDF"

        doc = models.Document(
            name=safe_name,
            title=doc_title,
            category=category,
            department=department,
            effective_date=effective_date,
            source_url=source_url,
            size=format_size(len(raw_bytes)),
            type=ext_type,
            status="pending",
            is_active=True,
            chunk_count=0,
            upload_date=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        try:
            pages = extract_pages_from_file(file_path)
            chunks = semantic_chunk_pages(
                pages=pages,
                doc_title=doc_title,
                category=category,
                doc_id=doc.id,
            )
            if not chunks:
                doc.status = "failed"
                db.commit()
                results.append({"name": safe_name, "doc_id": doc.id, "status": "empty", "chunks": 0})
                continue

            faiss_ids = VectorStore.add_chunks(chunks)
            doc.vector_ids = faiss_ids
            doc.chunk_count = len(faiss_ids)
            doc.status = "processed"
            db.commit()

            record_operation_log(
                db=db,
                event_type="DOC_UPLOAD",
                user=admin_user,
                query_preview=safe_name,
                status_code=200,
                detail=f"Đã nạp {len(faiss_ids)} chunks vào FAISS.",
            )

            results.append(
                {
                    "name": safe_name,
                    "doc_id": doc.id,
                    "title": doc_title,
                    "chunk_count": len(faiss_ids),
                    "status": "processed",
                }
            )
        except Exception as exc:
            doc.status = "failed"
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi xử lý pipeline RAG/Gemini Embedding cho file '{safe_name}': {exc}",
            )

    return {
        "EC": 0,
        "EM": "Tải lên và lập chỉ mục FAISS thành công!",
        "DT": results,
    }


def toggle_document_status(doc_id: int, is_active: bool, db: Session, admin_user: Optional[models.User] = None) -> dict:
    """Cho phep Admin vo hieu hoa (tat) tai lieu quy che cu khong cho RAG truy xuat."""
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu ID={doc_id}")

    doc.is_active = is_active
    doc.status = "processed" if is_active else "disabled"
    db.commit()

    record_operation_log(
        db=db,
        event_type="DOC_TOGGLE",
        user=admin_user,
        query_preview=doc.name,
        status_code=200,
        detail=f"is_active={is_active}",
    )

    return {
        "EC": 0,
        "EM": f"Đã {'kích hoạt' if is_active else 'vô hiệu hóa'} tài liệu '{doc.title}'!",
        "DT": {"id": doc.id, "isActive": doc.is_active, "status": doc.status},
    }


def delete_document_by_id(doc_id: int, db: Session, admin_user: Optional[models.User] = None) -> dict:
    """Xoa dong bo vectors khoi Pure FAISS, xoa file upload va xoa ban ghi khoi PostgreSQL."""
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        return {"EC": 1, "EM": f"Không tìm thấy tài liệu ID={doc_id}", "DT": []}

    removed_vecs = VectorStore.delete(
        vector_ids=document.vector_ids or [],
        source_filename=document.name,
    )

    # Chi xoa file vat ly neu nam trong thu muc upload cua Backend (khong xoa kho raw goc cua nhom RAG)
    uploaded_file = UPLOAD_DATA_DIR / document.name
    if uploaded_file.exists():
        uploaded_file.unlink()

    doc_name = document.name
    db.delete(document)
    db.commit()

    record_operation_log(
        db=db,
        event_type="DOC_DELETE",
        user=admin_user,
        query_preview=doc_name,
        status_code=200,
        detail=f"Đã xóa {removed_vecs} vectors khỏi FAISS.",
    )

    return {
        "EC": 0,
        "EM": f"Đã xóa tài liệu '{doc_name}' ({removed_vecs} vectors) thành công!",
        "DT": {"id": doc_id, "removed_vectors": removed_vecs},
    }


def get_operation_logs(db: Session, limit: int = 50, event_type: Optional[str] = None) -> dict:
    """Tab Nhat ky van hanh & Bao mat (Dac ta Phan 1.1C)."""
    q = db.query(models.OperationLog)
    if event_type:
        q = q.filter(models.OperationLog.event_type == event_type)
    rows = q.order_by(desc(models.OperationLog.created_at), desc(models.OperationLog.id)).limit(limit).all()

    return {
        "EC": 0,
        "EM": "Lấy nhật ký vận hành thành công!",
        "DT": [
            {
                "id": r.id,
                "username": r.username or "guest",
                "eventType": r.event_type,
                "intent": r.intent,
                "queryPreview": r.query_preview,
                "statusCode": r.status_code,
                "latencyMs": r.latency_ms,
                "detail": r.detail,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


def _find_physical_document_path(filename: str) -> Optional[Path]:
    """Tim file trong app/data/ hoac kho RAG/data/raw/ de phuc vu xem van ban goc."""
    direct_upload = UPLOAD_DATA_DIR / filename
    if direct_upload.exists():
        return direct_upload
    if REPO_RAW_DIR.exists():
        matches = list(REPO_RAW_DIR.rglob(filename))
        if matches:
            return matches[0]
    return None


def create_signed_url(doc_id: int, expires_in: int = 1800) -> str:
    """Tao Signed URL co thoi han de xem file tai lieu goc an toan (ke thua NCKH)."""
    payload = {"doc_id": doc_id, "exp": int(time.time()) + expires_in}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return f"/documents/{doc_id}/signed?token={token}"


def serve_signed_document(doc_id: int, token: str, db: Session) -> FileResponse:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("doc_id") != doc_id:
            raise HTTPException(status_code=403, detail="Token tài liệu không khớp.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Liên kết xem tài liệu đã hết hạn.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Token xem tài liệu không hợp lệ.")

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin tài liệu.")

    file_path = _find_physical_document_path(doc.name)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp vật lý trên máy chủ.")

    mime_type = {
        "PDF": "application/pdf",
        "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "TXT": "text/plain; charset=utf-8",
        "MD": "text/markdown; charset=utf-8",
    }.get(doc.type.upper(), "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{doc.name}"'},
    )
