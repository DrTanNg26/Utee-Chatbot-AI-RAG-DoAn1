from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.config.database import Base

# Tuong thich native JSONB tren PostgreSQL (nhu NCKH) va JSON tren SQLite khi test local
JSONBCompat = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    """
    Bang tai khoan hop nhat (Guest cookie / Sinh vien / Admin).
    Ke thua User + Admin cua repo NCKH va mo rong RBAC cho Sinh vien UTT.
    """
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(120), nullable=True)
    role = Column(String(20), nullable=False, default="student", index=True)  # guest | student | admin
    is_active = Column(Boolean, nullable=False, default=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Quan he 1-1 voi ho so sinh vien (neu role == 'student')
    student_profile = relationship(
        "Student",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    enrollments = relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")
    timetable_entries = relationship("Timetable", back_populates="user", cascade="all, delete-orphan")
    exam_entries = relationship("Exam", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")

    @property
    def formatted_last_login(self):
        if self.last_login:
            dt = self.last_login
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            vn_time = dt.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
            return vn_time.strftime("%d/%m/%Y %H:%M")
        return None


class Student(Base):
    """Ho so hoc vu ca nhan cua sinh vien UTT (chi truy cap duoc boi chinh chu tai khoan)."""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(32), unique=True, nullable=False, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    faculty = Column(String(150), nullable=False, default="Khoa Công nghệ Thông tin - UTT")
    major_name = Column(String(150), nullable=False, default="Công nghệ thông tin")
    class_name = Column(String(50), nullable=False)
    cohort = Column(String(20), nullable=False)
    total_credits_earned = Column(Integer, nullable=False, default=0)
    program_total_credits = Column(Integer, nullable=False, default=150)
    current_gpa_4 = Column(Float, nullable=False, default=0.0)
    current_gpa_10 = Column(Float, nullable=False, default=0.0)
    training_score = Column(Integer, nullable=False, default=80)
    academic_status = Column(String(50), nullable=False, default="Bình thường")

    user = relationship("User", back_populates="student_profile")


class Course(Base):
    """Danh muc hoc phan trong chuong trinh dao tao UTT."""
    __tablename__ = "courses"

    course_code = Column(String(32), primary_key=True, index=True)
    course_name = Column(String(200), nullable=False)
    credits = Column(Integer, nullable=False)
    major_name = Column(String(150), nullable=False, default="Công nghệ thông tin")
    semester_recommended = Column(Integer, nullable=True)
    prerequisite_code = Column(String(32), ForeignKey("courses.course_code", ondelete="SET NULL"), nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)


class Enrollment(Base):
    """Bang diem hoc phan va trang thai dat / hoc lai (diem F)."""
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_code", "semester", name="uq_enrollment_user_course_sem"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_code = Column(String(32), ForeignKey("courses.course_code", ondelete="CASCADE"), nullable=False)
    semester = Column(String(20), nullable=False)
    attendance_score = Column(Float, nullable=True)
    midterm_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    total_score_10 = Column(Float, nullable=True)
    total_score_4 = Column(Float, nullable=True)
    grade_letter = Column(String(5), nullable=True)  # A, B+, B, C+, C, D+, D, F, IP
    is_passed = Column(Boolean, nullable=False, default=True)
    status = Column(String(30), nullable=False, default="completed")  # completed | studying | retake_required

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course")


class Timetable(Base):
    """Thoi khoa bieu hoc tap trong tuan cua sinh vien."""
    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_code = Column(String(32), ForeignKey("courses.course_code", ondelete="CASCADE"), nullable=False)
    semester = Column(String(20), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 2 = Thu 2 ... 8 = Chu nhat
    day_label = Column(String(20), nullable=False)
    start_period = Column(Integer, nullable=False)
    end_period = Column(Integer, nullable=False)
    time_range = Column(String(40), nullable=False)
    room = Column(String(50), nullable=False)
    lecturer_name = Column(String(120), nullable=False)
    class_group = Column(String(50), nullable=True)

    user = relationship("User", back_populates="timetable_entries")
    course = relationship("Course")


class Exam(Base):
    """Lich thi ket thuc hoc phan cua sinh vien."""
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_code = Column(String(32), ForeignKey("courses.course_code", ondelete="CASCADE"), nullable=False)
    semester = Column(String(20), nullable=False)
    exam_date = Column(Date, nullable=False)
    exam_time = Column(String(40), nullable=False)
    room = Column(String(50), nullable=False)
    seat_number = Column(String(15), nullable=True)
    exam_format = Column(String(60), nullable=False)
    notes = Column(String(255), nullable=True)

    user = relationship("User", back_populates="exam_entries")
    course = relationship("Course")


class Document(Base):
    """
    Metadata tai lieu RAG va danh sach vector_ids trong FAISS.
    Ke thua truc tiep models.Document cua repo NCKH, bo sung trang thai is_active & metadata nguon UTT.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, default="Tài liệu UTT")
    department = Column(String(150), nullable=True, default="Phòng Đào tạo UTT")
    effective_date = Column(String(30), nullable=True)
    source_url = Column(String(500), nullable=True)
    size = Column(String(40), nullable=False, default="0 KB")
    type = Column(String(20), nullable=False, default="PDF")
    status = Column(String(30), nullable=False, default="processed")  # processed | pending | failed | disabled
    is_active = Column(Boolean, nullable=False, default=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    vector_ids = Column(JSONBCompat, nullable=True)
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    """Phien hoi thoai cua sinh vien / khach."""
    __tablename__ = "conversations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Cuộc trò chuyện mới")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """
    Lich su tin nhan chi tiet (Ke thua models.Message cua repo NCKH,
    bo sung conversation_id, sources trich dan RAG va structured_data cho Rich Cards).
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(20), nullable=False, default="user")  # user | assistant | system
    message = Column(Text, nullable=False)
    intent = Column(String(40), nullable=True)
    sources = Column(JSONBCompat, nullable=True)
    structured_data = Column(JSONBCompat, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")


class OperationLog(Base):
    """Nhat ky van hanh & kiem soat an toan truy cap (RBAC / Prompt Injection / Admin Actions)."""
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(64), nullable=True)
    event_type = Column(String(50), nullable=False, index=True)
    intent = Column(String(40), nullable=True)
    query_preview = Column(String(300), nullable=True)
    status_code = Column(Integer, nullable=False, default=200)
    latency_ms = Column(Float, nullable=True)
    detail = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
