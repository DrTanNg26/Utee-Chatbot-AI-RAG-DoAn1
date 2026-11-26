from datetime import datetime, timedelta, timezone
import os
from typing import Optional
import uuid

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models import User

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "utee_doan1_super_secret_jwt_key_change_in_production_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_user_from_token(token: str, db: Session) -> Optional[User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw = payload.get("user_id")
        sub = payload.get("sub")
    except JWTError:
        return None

    user: Optional[User] = None
    if user_id_raw:
        try:
            uid = uuid.UUID(str(user_id_raw))
            user = db.query(User).filter(User.id == uid).first()
        except ValueError:
            user = None

    if user is None and sub:
        user = (
            db.query(User)
            .filter((User.username == sub) | (User.email == sub))
            .first()
        )

    if user and not user.is_active:
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency bat buoc dang nhap: Trich xuat chinh xac User tu JWT Bearer Token.
    Tuyet doi khong tin user_id gui tuy y tu body/query cua Client.
    """
    user = _decode_user_from_token(token, db)
    if user is None or user.role == "guest":
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại!",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Dependency tuy chon cho API Chat:
    - Neu co Bearer Token hop le -> tra ve User da xac thuc (student/admin).
    - Neu khong co Token -> tra ve None (Guest vang lai chi duoc hoi thong tin cong khai RAG).
    """
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()
    if not raw_token:
        return None
    user = _decode_user_from_token(raw_token, db)
    if user and user.role != "guest":
        return user
    return None


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency chi cho phep tai khoan co role == 'admin'."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Truy cập bị từ chối: Chức năng này chỉ dành cho Quản trị viên (Admin).",
        )
    return current_user


async def change_user_password(
    current_user: User,
    current_password: str,
    new_password: str,
    db: Session,
) -> dict:
    if not verify_password(current_password, current_user.password_hash):
        return {
            "EC": 1,
            "EM": "Mật khẩu hiện tại không chính xác!",
            "DT": "",
        }
    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    return {
        "EC": 0,
        "EM": "Đổi mật khẩu thành công!",
        "DT": "",
    }
