from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class GradeItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_code: str
    course_name: str
    credits: int
    semester: str
    attendance_score: Optional[float] = None
    midterm_score: Optional[float] = None
    final_score: Optional[float] = None
    total_score_10: Optional[float] = None
    total_score_4: Optional[float] = None
    grade_letter: Optional[str] = None
    is_passed: bool
    status: str


class TimetableItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_code: str
    course_name: str
    credits: int
    semester: str
    day_of_week: int
    day_label: str
    start_period: int
    end_period: int
    time_range: str
    room: str
    lecturer_name: str
    class_group: Optional[str] = None


class ExamItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_code: str
    course_name: str
    credits: int
    semester: str
    exam_date: date
    exam_time: str
    room: str
    seat_number: Optional[str] = None
    exam_format: str
    notes: Optional[str] = None


class StudentGradesOverviewDTO(BaseModel):
    student_code: str
    full_name: str
    major_name: str
    class_name: str
    total_credits_earned: int
    program_total_credits: int
    current_gpa_4: float
    current_gpa_10: float
    training_score: int
    academic_status: str
    passed_count: int
    failed_count: int
    grades: List[GradeItemDTO]
    retake_courses: List[GradeItemDTO]
