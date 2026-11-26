"""
routes.py - Dinh nghia cac API Quan tri (Admin) cho ca 2 chuan:
1. Chuan ke thua repo NCKH (/admin/document/read, /admin/document/add, /admin/document/delete, /admin/stats, /admin/chatbotcfg/*)
2. Chuan Dac ta Ky thuat UTee (/api/v1/admin/documents, /api/v1/admin/documents/{id}, /api/v1/admin/logs, /api/v1/admin/stats)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.auth_service import create_admin
from app.auth.util import change_user_password, get_current_admin
from app.config.database import get_db
from app.config_manager import load_config, save_config
from app.models import User
from app.schemas.admin import DocumentToggleRequest
from app.schemas.auth import AdminCreate, ChangePasswordSchema
import app.services.admin_service as admin_service

# 1. Router NCKH (/admin/*)
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin Management (NCKH Compatible)"],
    dependencies=[Depends(get_current_admin)],
)

# 2. Router UTee Spec v1 (/api/v1/admin/*)
v1_admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Management (v1)"],
    dependencies=[Depends(get_current_admin)],
)


@admin_router.get("/document/read")
@v1_admin_router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    return admin_service.get_all_documents(db)


@admin_router.post("/document/add")
@v1_admin_router.post("/documents")
async def upload_documents(
    files: List[UploadFile] = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("Tài liệu UTT"),
    department: str = Form("Phòng Đào tạo UTT"),
    effective_date: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await admin_service.add_documents(
        files=files,
        db=db,
        title=title,
        category=category,
        department=department,
        effective_date=effective_date,
        source_url=source_url,
        admin_user=current_admin,
    )


@admin_router.post("/document/delete")
async def delete_document_nckh(
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = await request.json()
    doc_id = data.get("id")
    if doc_id is None:
        raise HTTPException(status_code=400, detail="Thiếu tham số id tài liệu cần xóa.")
    return admin_service.delete_document_by_id(int(doc_id), db, admin_user=current_admin)


@v1_admin_router.delete("/documents/{doc_id}")
def delete_document_v1(
    doc_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return admin_service.delete_document_by_id(doc_id, db, admin_user=current_admin)


@v1_admin_router.patch("/documents/{doc_id}/toggle")
def toggle_document_v1(
    doc_id: int,
    payload: DocumentToggleRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return admin_service.toggle_document_status(
        doc_id=doc_id,
        is_active=payload.is_active,
        db=db,
        admin_user=current_admin,
    )


@admin_router.get("/stats")
@v1_admin_router.get("/stats")
def get_admin_stats(
    startDate: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    endDate: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    return admin_service.stats_service(startDate, endDate)


@v1_admin_router.get("/logs")
def get_admin_operation_logs(
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return admin_service.get_operation_logs(db=db, limit=limit, event_type=event_type)


@admin_router.post("/change-password")
async def admin_change_password(
    password_data: ChangePasswordSchema,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return await change_user_password(
        current_user=current_admin,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
        db=db,
    )


@admin_router.post("/register")
def register_new_admin(admin: AdminCreate, db: Session = Depends(get_db)):
    created = create_admin(
        db=db,
        username=admin.username,
        email=admin.email,
        password=admin.password,
        full_name=admin.full_name or "Quản trị viên UTT",
    )
    return {
        "EC": 0,
        "EM": "Create new admin success!",
        "DT": {
            "username": created.username,
            "email": created.email,
            "last_login": created.last_login,
            "formatted_last_login": created.formatted_last_login,
        },
    }


@admin_router.get("/documents/{doc_id}/generate_link")
@v1_admin_router.get("/documents/{doc_id}/generate_link")
def generate_doc_link(doc_id: int):
    signed_url = admin_service.create_signed_url(doc_id, expires_in=1800)
    return {
        "EC": 0,
        "EM": "Create signed url success!",
        "DT": {"url": signed_url},
    }


@admin_router.get("/chatbotcfg/get")
@v1_admin_router.get("/config")
def get_chatbot_cfg():
    return {
        "EC": 0,
        "EM": "Get chatbot cfg success!",
        "DT": load_config(),
    }


@admin_router.post("/chatbotcfg/post")
@v1_admin_router.put("/config")
async def update_chatbot_cfg(request: Request):
    data = await request.json()
    cfg_payload = data.get("config", data) if isinstance(data, dict) else {}
    updated = save_config(cfg_payload)
    return {
        "EC": 0,
        "EM": "Update chatbot cfg success!",
        "DT": updated,
    }
