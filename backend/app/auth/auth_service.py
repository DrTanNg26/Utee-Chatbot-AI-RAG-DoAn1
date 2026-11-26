from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.util import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models import User
from app.schemas.auth import StudentSummaryDTO, UserResponseDTO


def build_user_dto(user: User) -> UserResponseDTO:
    sp = user.student_profile
    student_dto = StudentSummaryDTO.model_validate(sp) if sp else None
    return UserResponseDTO(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        major=sp.major_name if sp else ("Quản trị hệ thống" if user.role == "admin" else None),
        faculty=sp.faculty if sp else ("Phòng Đào tạo - UTT" if user.role == "admin" else None),
        last_login=user.last_login,
        formatted_last_login=user.formatted_last_login,
        student_profile=student_dto,
    )


def create_admin(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str = "Quản trị viên UTT",
) -> User:
    try:
        existing = (
            db.query(User)
            .filter(
                (func.lower(User.username) == username.strip().lower())
                | (func.lower(User.email) == email.strip().lower())
            )
            .first()
        )
        if existing:
            if existing.username.lower() == username.strip().lower():
                raise HTTPException(status_code=400, detail="Username đã tồn tại!")
            raise HTTPException(status_code=400, detail="Email đã tồn tại!")

        db_admin = User(
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=get_password_hash(password),
            full_name=full_name,
            role="admin",
            is_active=True,
            last_login=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")),
        )
        db.add(db_admin)
        db.commit()
        db.refresh(db_admin)
        return db_admin
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Lỗi toàn vẹn dữ liệu tài khoản.")


def authenticate_user(
    db: Session,
    identifier: str,
    password: str,
) -> dict:
    """
    Xac thuc Sinh vien hoac Admin bang username (MSSV) hoac email + mat khau Bcrypt.
    Cap phat JWT chua user_id va role.
    """
    ident = identifier.strip()
    user: Optional[User] = (
        db.query(User)
        .filter(
            (func.lower(User.username) == ident.lower())
            | (func.lower(User.email) == ident.lower())
        )
        .first()
    )

    if not user or not user.is_active or user.role == "guest" or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Mã sinh viên / Tài khoản hoặc mật khẩu không chính xác!",
        )

    now_vn = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    user.last_login = now_vn
    user.last_seen = now_vn
    db.commit()
    db.refresh(user)

    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": str(user.id),
            "role": user.role,
        },
        expires_delta=expires,
    )

    user_dto = build_user_dto(user)
    payload_dict = {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_dto.model_dump(mode="json"),
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "EC": 0,
        "EM": "Đăng nhập thành công!",
        "user": user_dto,
        "DT": payload_dict,
    }


def list_demo_accounts(db: Session) -> list[dict]:
    """
    Tra ve danh sach cac tai khoan Demo phuc vu One-Click Demo Switcher & LoginView
    (Khong bao gio tra ve password_hash).
    """
    demo_users = (
        db.query(User)
        .filter(User.role.in_(["student", "admin"]), User.is_active.is_(True))
        .order_by(User.role.desc(), User.username.asc())
        .all()
    )

    scenario_hints = {
        "21010001": "Sinh viên Giỏi (GPA 3.45, không nợ môn, đủ lịch học & lịch thi)",
        "21010002": "Sinh viên Nợ môn (Nợ 2 môn điểm F: Toán 2 & Lập trình C -> Demo SQL + RAG)",
        "23010003": "Sinh viên Khóa mới Năm 1 (Chưa có điểm tổng kết, có TKB tuần đầu)",
        "75DCTT12345": "Sinh viên CNTT (Khớp nút Demo trên giao diện Live2D Frontend)",
        "74DCOT99881": "Sinh viên Cơ khí Ô tô (Khớp nút Demo trên giao diện Live2D Frontend)",
        "admin_demo": "Quản trị viên UTT (Upload/quản lý tài liệu RAG & Nhật ký bảo mật)",
    }

    items = []
    for u in demo_users:
        sp = u.student_profile
        items.append(
            {
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "major": sp.major_name if sp else "Quản trị hệ thống",
                "faculty": sp.faculty if sp else "Phòng Đào tạo - UTT",
                "class_name": sp.class_name if sp else None,
                "demo_password": "utt123456",
                "scenario": scenario_hints.get(u.username, "Tài khoản thử nghiệm hệ thống"),
            }
        )
    return items
