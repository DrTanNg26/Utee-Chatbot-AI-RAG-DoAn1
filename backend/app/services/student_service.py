"""
student_service.py - Dich vu truy van du lieu hoc vu ca nhan co kiem soat phan quyen (RBAC).
NGUYEN TAC BAO MAT COT LOI:
- Moi ham CHI nhan user_id tu User da xac thuc qua JWT (get_current_user).
- Chi chay truy van tham so hoa SQLAlchemy ORM (Chong 100% SQL Injection & Hoi cheo tai khoan).
"""

from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.util import get_current_user
from app.config.database import get_db
from app.models import Course, Enrollment, Exam, Student, Timetable, User

student_router = APIRouter(
    prefix="/api/v1/student",
    tags=["Student Academic Data (v1)"],
)


def get_student_profile(db: Session, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Tra ve thong tin nganh, khoa, lop, so tin chi tich luy va GPA cua chinh user_id."""
    user = db.query(User).filter(User.id == user_id).first()
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if not user or not student:
        return None

    program_courses = (
        db.query(Course)
        .filter(Course.major_name == student.major_name)
        .order_by(Course.semester_recommended.asc(), Course.course_code.asc())
        .all()
    )

    remaining_credits = max(student.program_total_credits - student.total_credits_earned, 0)
    progress_pct = round((student.total_credits_earned / max(student.program_total_credits, 1)) * 100, 1)

    return {
        "student_code": student.student_code,
        "full_name": user.full_name or user.username,
        "faculty": student.faculty,
        "major_name": student.major_name,
        "class_name": student.class_name,
        "cohort": student.cohort,
        "total_credits_earned": student.total_credits_earned,
        "program_total_credits": student.program_total_credits,
        "remaining_credits": remaining_credits,
        "progress_percent": progress_pct,
        "current_gpa_4": round(student.current_gpa_4, 2),
        "current_gpa_10": round(student.current_gpa_10, 2),
        "training_score": student.training_score,
        "academic_status": student.academic_status,
        "program_courses": [
            {
                "course_code": c.course_code,
                "course_name": c.course_name,
                "credits": c.credits,
                "semester_recommended": c.semester_recommended,
                "is_required": c.is_required,
            }
            for c in program_courses
        ],
    }


def get_student_grades(db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
    """
    Tra ve bang diem cac hoc phan da hoan thanh va loc rieng danh sach mon diem F / chua dat
    can hoc lai cua chinh user_id.
    """
    profile = get_student_profile(db, user_id)
    rows = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_code == Course.course_code)
        .filter(Enrollment.user_id == user_id)
        .order_by(Enrollment.semester.desc(), Course.course_code.asc())
        .all()
    )

    grades: List[Dict[str, Any]] = []
    retake_courses: List[Dict[str, Any]] = []

    for enr, course in rows:
        item = {
            "course_code": course.course_code,
            "course_name": course.course_name,
            "credits": course.credits,
            "semester": enr.semester,
            "attendance_score": enr.attendance_score,
            "midterm_score": enr.midterm_score,
            "final_score": enr.final_score,
            "total_score_10": enr.total_score_10,
            "total_score_4": enr.total_score_4,
            "grade_letter": enr.grade_letter,
            "is_passed": enr.is_passed,
            "status": enr.status,
        }
        grades.append(item)
        if not enr.is_passed or enr.grade_letter == "F" or enr.status == "retake_required":
            retake_courses.append(item)

    passed_count = sum(1 for g in grades if g["is_passed"] and g["status"] == "completed")
    failed_count = len(retake_courses)
    failed_credits = sum(g["credits"] for g in retake_courses)

    return {
        "profile": profile,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "failed_credits": failed_credits,
        "grades": grades,
        "retake_courses": retake_courses,
    }


def get_student_timetable(
    db: Session,
    user_id: uuid.UUID,
    semester: Optional[str] = None,
    day_of_week: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Tra ve thoi khoa bieu tuan cua chinh user_id."""
    q = (
        db.query(Timetable, Course)
        .join(Course, Timetable.course_code == Course.course_code)
        .filter(Timetable.user_id == user_id)
    )
    if semester:
        q = q.filter(Timetable.semester == semester)
    if day_of_week is not None:
        q = q.filter(Timetable.day_of_week == day_of_week)

    rows = q.order_by(Timetable.day_of_week.asc(), Timetable.start_period.asc()).all()
    return [
        {
            "course_code": course.course_code,
            "course_name": course.course_name,
            "credits": course.credits,
            "semester": tt.semester,
            "day_of_week": tt.day_of_week,
            "day_label": tt.day_label,
            "start_period": tt.start_period,
            "end_period": tt.end_period,
            "time_range": tt.time_range,
            "room": tt.room,
            "lecturer_name": tt.lecturer_name,
            "class_group": tt.class_group,
        }
        for tt, course in rows
    ]


def get_student_exam_schedule(
    db: Session,
    user_id: uuid.UUID,
    semester: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Tra ve danh sach mon thi, ngay thi, gio thi, phong thi sap toi cua chinh user_id."""
    q = (
        db.query(Exam, Course)
        .join(Course, Exam.course_code == Course.course_code)
        .filter(Exam.user_id == user_id)
    )
    if semester:
        q = q.filter(Exam.semester == semester)

    rows = q.order_by(Exam.exam_date.asc(), Exam.exam_time.asc()).all()
    return [
        {
            "course_code": course.course_code,
            "course_name": course.course_name,
            "credits": course.credits,
            "semester": ex.semester,
            "exam_date": ex.exam_date.isoformat() if ex.exam_date else "",
            "exam_time": ex.exam_time,
            "room": ex.room,
            "seat_number": ex.seat_number,
            "exam_format": ex.exam_format,
            "notes": ex.notes,
        }
        for ex, course in rows
    ]


# ================= REST Endpoints (/api/v1/student/*) =================


@student_router.get("/profile")
def api_get_student_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_student_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Tài khoản này không có hồ sơ sinh viên học vụ.")
    return {"EC": 0, "EM": "Lấy hồ sơ sinh viên thành công!", "DT": profile}


@student_router.get("/grades")
def api_get_student_grades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = get_student_grades(db, current_user.id)
    if not data["profile"]:
        raise HTTPException(status_code=404, detail="Tài khoản này không có bảng điểm sinh viên.")
    return {"EC": 0, "EM": "Lấy bảng điểm & học phần cần học lại thành công!", "DT": data}


@student_router.get("/timetable")
def api_get_student_timetable(
    semester: Optional[str] = Query(None, description="Học kỳ (vd: 2026_1)"),
    day_of_week: Optional[int] = Query(None, ge=2, le=8, description="Thứ trong tuần (2..8)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = get_student_timetable(db, current_user.id, semester=semester, day_of_week=day_of_week)
    return {"EC": 0, "EM": "Lấy thời khóa biểu thành công!", "DT": items}


@student_router.get("/exams")
def api_get_student_exams(
    semester: Optional[str] = Query(None, description="Học kỳ (vd: 2026_1)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = get_student_exam_schedule(db, current_user.id, semester=semester)
    return {"EC": 0, "EM": "Lấy lịch thi học kỳ thành công!", "DT": items}
