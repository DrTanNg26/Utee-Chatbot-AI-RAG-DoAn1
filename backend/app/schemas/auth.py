from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    """
    Ho tro dang nhap linh hoat bang:
    - username (Ma sinh vien / username, vd: '75DCTT12345', '21010001', 'admin_demo')
    - hoac email (tuong thich AdminLogin cua repo NCKH, vd: 'admin@utt.edu.vn')
    """
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def check_identifier(self):
        if not (self.username and self.username.strip()) and not (self.email and self.email.strip()):
            raise ValueError("Vui lòng nhập Mã số sinh viên (username) hoặc Email đăng nhập.")
        return self


class StudentSummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_code: str
    faculty: str
    major_name: str
    class_name: str
    cohort: str
    total_credits_earned: int
    program_total_credits: int
    current_gpa_4: float
    current_gpa_10: float
    training_score: int
    academic_status: str


class UserResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    major: Optional[str] = None
    faculty: Optional[str] = None
    last_login: Optional[datetime] = None
    formatted_last_login: Optional[str] = None
    student_profile: Optional[StudentSummaryDTO] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    EC: int = 0
    EM: str = "Đăng nhập thành công!"
    user: UserResponseDTO
    DT: Optional[dict] = None


class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str


class AdminCreate(BaseModel):
    username: str
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str
    full_name: Optional[str] = "Quản trị viên UTT"
