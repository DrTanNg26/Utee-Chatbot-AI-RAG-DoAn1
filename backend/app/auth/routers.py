from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.auth_service import authenticate_user, build_user_dto, list_demo_accounts
from app.auth.util import change_user_password, get_current_user
from app.config.database import get_db
from app.models import User
from app.schemas.auth import ChangePasswordSchema, LoginRequest, TokenResponse, UserResponseDTO

# Router ke thua duong dan /auth/* cua repo NCKH
router = APIRouter(prefix="/auth", tags=["Authentication (NCKH Compatible)"])

# Router chuan RESTful v1 theo Dac ta Ky thuat UTee (/api/v1/auth/*)
v1_auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication (v1)"])


@router.post("/login", response_model=TokenResponse)
@v1_auth_router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    identifier = credentials.username or credentials.email or ""
    return authenticate_user(db, identifier=identifier, password=credentials.password)


@router.get("/me", response_model=UserResponseDTO)
@v1_auth_router.get("/me", response_model=UserResponseDTO)
def read_users_me(current_user: User = Depends(get_current_user)):
    return build_user_dto(current_user)


@router.get("/demo-accounts")
@v1_auth_router.get("/demo-accounts")
def get_demo_accounts(db: Session = Depends(get_db)):
    accounts = list_demo_accounts(db)
    return {
        "EC": 0,
        "EM": "Lấy danh sách tài khoản demo thành công!",
        "DT": accounts,
    }


@router.post("/change-password")
@v1_auth_router.post("/change-password")
async def update_password(
    payload: ChangePasswordSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await change_user_password(
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        db=db,
    )
