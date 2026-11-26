"""
security.py - Cac lop bao ve An toan Thong tin (Tuan 8 & Nguyen tac Cot loi Do an 1):
1. Chong Prompt Injection & Jailbreak (chan tiet lo System Prompt / API Key / gia mao quyen).
2. Chong Hoi cheo Tai khoan (Cross-Account Data Leak Protection: Tai khoan A hoi du lieu cua B).
3. Ghi nhat ky an toan (OperationLog) khong chua du lieu nhay cam.
"""

import re
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import OperationLog, Student, User

# Cac mau tan cong Prompt Injection pho bien (Tieng Viet & Tieng Anh)
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+)?(previous|system)\s+(instructions|prompts)",
    r"bỏ\s+qua\s+(mọi|tất\s+cả|toàn\s+bộ)?\s*(hướng\s+dẫn|quy\s+tắc|lệnh|chỉ\s+dẫn)\s*(trước|trên|hệ\s+thống)?",
    r"(in\s+ra|hiển\s+thị|tiết\s+lộ|cho\s+xem|reveal|show|print)\s+(toàn\s+bộ\s+)?(system\s*prompt|api\s*key|secret\s*key|jwt_secret|mật\s+khẩu\s+băm)",
    r"(giả\s+sử|đóng\s+vai|bây\s+giờ)\s+(tôi|mình|cậu|bạn)\s+là\s+(admin|quản\s+trị\s+viên|hiệu\s+trưởng|root)",
    r"bypass\s+(auth|rbac|permission|security)",
    r"select\s+\*\s+from\s+users",
    r"drop\s+table\s+",
    r"union\s+select\s+",
]

# Regex bat ma so sinh vien UTT pho bien: vd 21010001, 23010003, 75DCTT12345, 74DCOT99881, 72DCHT21...
STUDENT_CODE_REGEX = re.compile(
    r"\b(\d{8}|\d{2}[a-zA-Z]{3,5}\d{3,6})\b",
    flags=re.IGNORECASE,
)


def detect_prompt_injection(query: str) -> Tuple[bool, Optional[str]]:
    """Kiem tra dau hieu Prompt Injection hoac SQL Injection tho trong cau hoi."""
    q_norm = query.strip().lower()
    for pat in PROMPT_INJECTION_PATTERNS:
        if re.search(pat, q_norm, flags=re.IGNORECASE):
            return True, f"Phát hiện mẫu truy vấn vi phạm chính sách an toàn ({pat[:35]}...)"
    return False, None


def detect_cross_account_attempt(
    query: str,
    current_user: Optional[User],
    db: Session,
) -> Tuple[bool, Optional[str]]:
    """
    Rao chan 2 (Chong hoi cheo):
    Neu nguoi dung hoi thong tin ca nhan nhung nhac toi MSSV hoac Ho ten cua sinh vien khac,
    chan ngay lap tuc o tang Backend truoc khi truy van CSDL hay goi LLM!
    """
    q_lower = query.strip().lower()
    own_code = ""
    own_name = ""

    if current_user:
        own_code = (current_user.username or "").strip().lower()
        own_name = (current_user.full_name or "").strip().lower()
        if current_user.student_profile and current_user.student_profile.student_code:
            own_code = current_user.student_profile.student_code.strip().lower()

    # 1. Kiem tra ma sinh vien xuat hien trong cau hoi
    mentioned_codes = [m.group(1).lower() for m in STUDENT_CODE_REGEX.finditer(query)]
    for code in mentioned_codes:
        if code != own_code:
            return True, f"Từ chối truy cập chéo mã số '{code.upper()}' không thuộc phiên xác thực hiện tại."

    # 2. Kiem tra cum tu hoi ho so nguoi khac ro rang
    other_person_patterns = [
        r"(điểm|bảng\s+điểm|lịch\s+học|thời\s+khóa\s+biểu|lịch\s+thi|hồ\s+sơ|gpa|môn\s+nợ)\s+của\s+(bạn|sinh\s+viên|anh|chị|em)\s+([a-zà-ỹđ]+\s+){1,4}",
        r"xem\s+(điểm|lịch\s+học|lịch\s+thi|hồ\s+sơ)\s+(của\s+)?(bạn\s+khác|người\s+khác|tài\s+khoản\s+khác)",
    ]
    for pat in other_person_patterns:
        if re.search(pat, q_lower):
            # Dam bao khong chan nham neu nguoi dung tu xung ten minh
            if own_name and own_name in q_lower:
                continue
            return True, "Từ chối yêu cầu tra cứu thông tin học tập của cá nhân khác."

    # 3. Doi chieu ten day du cua cac sinh vien trong DB (khong tiet lo B co ton tai hay khong cho client)
    personal_keywords = ("điểm", "lịch học", "thời khóa biểu", "lịch thi", "học lại", "nợ môn", "hồ sơ", "gpa", "tín chỉ tích lũy")
    if any(kw in q_lower for kw in personal_keywords):
        other_students = (
            db.query(User.full_name, Student.student_code)
            .join(Student, Student.user_id == User.id)
            .all()
        )
        for full_name, st_code in other_students:
            if not full_name:
                continue
            fn_low = full_name.strip().lower()
            sc_low = (st_code or "").strip().lower()
            if fn_low and fn_low != own_name and fn_low in q_lower:
                return True, "Từ chối truy cập dữ liệu cá nhân không thuộc tài khoản đang đăng nhập."
            if sc_low and sc_low != own_code and sc_low in q_lower:
                return True, "Từ chối truy cập dữ liệu cá nhân không thuộc tài khoản đang đăng nhập."

    return False, None


def record_operation_log(
    db: Session,
    event_type: str,
    user: Optional[User] = None,
    intent: Optional[str] = None,
    query_preview: Optional[str] = None,
    status_code: int = 200,
    latency_ms: Optional[float] = None,
    detail: Optional[str] = None,
) -> None:
    """Ghi nhat ky van hanh co chon loc (khong luu diem chi tiet hay thong tin nhay cam)."""
    try:
        preview_safe = (query_preview or "").strip()[:280] if query_preview else None
        log_entry = OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else "guest",
            event_type=event_type,
            intent=intent,
            query_preview=preview_safe,
            status_code=status_code,
            latency_ms=latency_ms,
            detail=(detail or "")[:480] if detail else None,
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()
