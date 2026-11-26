"""
seed_db.py - Script khoi tao va dung lai toan bo Co so du lieu + Mock Data kich ban Demo tu dau.
Chay lenh:
    python seed_db.py           # Khoi tao neu chua co (Idempotent)
    python seed_db.py --reset   # Xoa va dung lai moi hoan toan tu dau
"""

from collections import defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

from app.auth.util import get_password_hash
from app.config.database import Base, SessionLocal, SQLALCHEMY_DATABASE_URL, engine
from app.models import (
    Course,
    Document,
    Enrollment,
    Exam,
    Student,
    Timetable,
    User,
)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
RAG_RAW_DIR = REPO_ROOT / "RAG" / "data" / "raw"
RAG_META_FILE = REPO_ROOT / "RAG" / "data" / "vectorstore" / "chunks_metadata.json"


def _fmt_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024**2:
        return f"{num / 1024:.1f} KB"
    return f"{num / 1024**2:.1f} MB"


def seed_all(reset: bool = False) -> None:
    print("=" * 72)
    print("KHỞI TẠO CƠ SỞ DỮ LIỆU & MOCK DATA DEMO — UTEE CHATBOT BACKEND")
    print(f"Database URL: {SQLALCHEMY_DATABASE_URL}")
    print("=" * 72)

    if reset:
        print("[RESET] Đang xóa toàn bộ bảng cũ để dựng lại từ đầu...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. SEED COURSES (Danh muc hoc phan UTT)
        courses_seed = [
            Course(course_code="DC1CB11", course_name="Toán cao cấp 1 (Toán 1)", credits=4, major_name="Công nghệ thông tin", semester_recommended=1),
            Course(course_code="DC1CB41", course_name="Toán cao cấp 2 (Toán 2)", credits=4, major_name="Công nghệ thông tin", semester_recommended=2, prerequisite_code="DC1CB11"),
            Course(course_code="DC1TT21", course_name="Vật lý đại cương", credits=3, major_name="Công nghệ thông tin", semester_recommended=1),
            Course(course_code="DC1TT44", course_name="Tin học cơ sở", credits=3, major_name="Công nghệ thông tin", semester_recommended=1),
            Course(course_code="DC2TT23", course_name="Lập trình C++ (Ngôn ngữ lập trình C)", credits=3, major_name="Công nghệ thông tin", semester_recommended=2),
            Course(course_code="DC2HT42", course_name="Toán rời rạc", credits=3, major_name="Công nghệ thông tin", semester_recommended=2),
            Course(course_code="DC2HT26", course_name="Cấu trúc dữ liệu và giải thuật", credits=3, major_name="Công nghệ thông tin", semester_recommended=3, prerequisite_code="DC2TT23"),
            Course(course_code="DC2TT22", course_name="Nhập môn cơ sở dữ liệu", credits=3, major_name="Công nghệ thông tin", semester_recommended=3),
            Course(course_code="DC2HT13", course_name="Nhập môn mạng máy tính", credits=3, major_name="Công nghệ thông tin", semester_recommended=4),
            Course(course_code="DC2HT36", course_name="Lập trình trên môi trường Web", credits=3, major_name="Công nghệ thông tin", semester_recommended=5),
            Course(course_code="DC3HT21", course_name="Hệ quản trị cơ sở dữ liệu", credits=3, major_name="Công nghệ thông tin", semester_recommended=5, prerequisite_code="DC2TT22"),
            Course(course_code="DC3HT12", course_name="Trí tuệ nhân tạo", credits=3, major_name="Công nghệ thông tin", semester_recommended=6),
            Course(course_code="DC3HT41", course_name="Kiểm thử phần mềm", credits=3, major_name="Công nghệ thông tin", semester_recommended=6),
            # Hoc phan nganh Co khi O to (cho tai khoan 74DCOT99881 tren Frontend)
            Course(course_code="CK2OT11", course_name="Lý thuyết Ô tô", credits=3, major_name="Công nghệ kỹ thuật Ô tô", semester_recommended=4),
            Course(course_code="CK2OT22", course_name="Kết cấu và tính toán động cơ đốt trong", credits=4, major_name="Công nghệ kỹ thuật Ô tô", semester_recommended=4),
            Course(course_code="CK3OT15", course_name="Trang bị điện và điện tử trên Ô tô", credits=3, major_name="Công nghệ kỹ thuật Ô tô", semester_recommended=5),
        ]

        for c in courses_seed:
            if not db.query(Course).filter(Course.course_code == c.course_code).first():
                db.add(c)
        db.commit()
        print(f"[1/4] Đã đảm bảo danh mục {db.query(Course).count()} học phần đào tạo.")

        # 2. SEED USERS & STUDENTS (6 tai khoan Demo chuan Dac ta + Frontend)
        default_pw_hash = get_password_hash("utt123456")

        users_specs = [
            {
                "username": "admin_demo",
                "email": "admin@utt.edu.vn",
                "full_name": "Quản trị viên Hệ thống UTT",
                "role": "admin",
                "student": None,
            },
            {
                "username": "21010001",
                "email": "21010001@st.utt.edu.vn",
                "full_name": "Nguyễn Văn A",
                "role": "student",
                "student": {
                    "student_code": "21010001",
                    "faculty": "Khoa Công nghệ Thông tin - UTT",
                    "major_name": "Công nghệ thông tin",
                    "class_name": "72DCHT21",
                    "cohort": "K72",
                    "total_credits_earned": 70,
                    "program_total_credits": 150,
                    "current_gpa_4": 3.45,
                    "current_gpa_10": 8.42,
                    "training_score": 88,
                    "academic_status": "Bình thường (Đủ điều kiện xét Học bổng Giỏi)",
                },
            },
            {
                "username": "21010002",
                "email": "21010002@st.utt.edu.vn",
                "full_name": "Trần Thị B",
                "role": "student",
                "student": {
                    "student_code": "21010002",
                    "faculty": "Khoa Công nghệ Thông tin - UTT",
                    "major_name": "Công nghệ thông tin",
                    "class_name": "72DCHT22",
                    "cohort": "K72",
                    "total_credits_earned": 58,
                    "program_total_credits": 150,
                    "current_gpa_4": 2.15,
                    "current_gpa_10": 5.85,
                    "training_score": 72,
                    "academic_status": "Cần đăng ký học lại 2 học phần điểm F",
                },
            },
            {
                "username": "23010003",
                "email": "23010003@st.utt.edu.vn",
                "full_name": "Lê Văn C",
                "role": "student",
                "student": {
                    "student_code": "23010003",
                    "faculty": "Khoa Công nghệ Thông tin - UTT",
                    "major_name": "Công nghệ thông tin",
                    "class_name": "75DCTT21",
                    "cohort": "K75",
                    "total_credits_earned": 0,
                    "program_total_credits": 150,
                    "current_gpa_4": 0.0,
                    "current_gpa_10": 0.0,
                    "training_score": 80,
                    "academic_status": "Sinh viên Năm 1 (Đang học kỳ đầu tiên)",
                },
            },
            {
                "username": "75DCTT12345",
                "email": "75dctt12345@st.utt.edu.vn",
                "full_name": "Phạm Minh Đức",
                "role": "student",
                "student": {
                    "student_code": "75DCTT12345",
                    "faculty": "Khoa Công nghệ Thông tin - UTT",
                    "major_name": "Công nghệ thông tin",
                    "class_name": "75DCTT23",
                    "cohort": "K75",
                    "total_credits_earned": 32,
                    "program_total_credits": 150,
                    "current_gpa_4": 3.25,
                    "current_gpa_10": 8.05,
                    "training_score": 85,
                    "academic_status": "Bình thường",
                },
            },
            {
                "username": "74DCOT99881",
                "email": "74dcot99881@st.utt.edu.vn",
                "full_name": "Hoàng Quốc Bảo",
                "role": "student",
                "student": {
                    "student_code": "74DCOT99881",
                    "faculty": "Khoa Cơ khí - Ô tô UTT",
                    "major_name": "Công nghệ kỹ thuật Ô tô",
                    "class_name": "74DCOT21",
                    "cohort": "K74",
                    "total_credits_earned": 54,
                    "program_total_credits": 150,
                    "current_gpa_4": 2.75,
                    "current_gpa_10": 7.10,
                    "training_score": 78,
                    "academic_status": "Cần học lại 1 học phần điểm F",
                },
            },
        ]

        user_map: dict[str, User] = {}
        for spec in users_specs:
            u = db.query(User).filter(User.username == spec["username"]).first()
            if not u:
                u = User(
                    username=spec["username"],
                    email=spec["email"],
                    password_hash=default_pw_hash,
                    full_name=spec["full_name"],
                    role=spec["role"],
                    is_active=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)

            if spec["student"] and not db.query(Student).filter(Student.user_id == u.id).first():
                st = Student(user_id=u.id, **spec["student"])
                db.add(st)
                db.commit()

            user_map[spec["username"]] = u

        print(f"[2/4] Đã khởi tạo {len(user_map)} tài khoản Demo (mật khẩu mặc định: utt123456).")

        # 3. SEED ENROLLMENTS (GRADES), TIMETABLE & EXAMS
        u_good = user_map["21010001"]
        u_debt = user_map["21010002"]
        u_fresh = user_map["23010003"]
        u_fe_cntt = user_map["75DCTT12345"]
        u_fe_oto = user_map["74DCOT99881"]

        if db.query(Enrollment).count() == 0:
            enrollments_seed = [
                # Sinh vien Gioi 21010001 (Khong no mon nao)
                Enrollment(user_id=u_good.id, course_code="DC1CB11", semester="2025_1", attendance_score=10.0, midterm_score=8.5, final_score=8.8, total_score_10=8.8, total_score_4=3.7, grade_letter="A", is_passed=True, status="completed"),
                Enrollment(user_id=u_good.id, course_code="DC2TT23", semester="2025_1", attendance_score=9.5, midterm_score=8.0, final_score=8.5, total_score_10=8.5, total_score_4=3.7, grade_letter="A", is_passed=True, status="completed"),
                Enrollment(user_id=u_good.id, course_code="DC2HT26", semester="2025_2", attendance_score=9.0, midterm_score=8.2, final_score=8.0, total_score_10=8.2, total_score_4=3.5, grade_letter="B+", is_passed=True, status="completed"),
                Enrollment(user_id=u_good.id, course_code="DC2TT22", semester="2025_2", attendance_score=10.0, midterm_score=8.5, final_score=8.6, total_score_10=8.7, total_score_4=3.7, grade_letter="A", is_passed=True, status="completed"),
                Enrollment(user_id=u_good.id, course_code="DC2HT36", semester="2026_1", attendance_score=9.0, midterm_score=8.0, final_score=7.8, total_score_10=8.0, total_score_4=3.5, grade_letter="B+", is_passed=True, status="completed"),

                # Sinh vien No mon 21010002 (No 2 mon diem F: Toan cao cap 2 & Lap trinh C++)
                Enrollment(user_id=u_debt.id, course_code="DC1CB11", semester="2025_1", attendance_score=8.0, midterm_score=6.5, final_score=6.0, total_score_10=6.4, total_score_4=2.3, grade_letter="C", is_passed=True, status="completed"),
                Enrollment(user_id=u_debt.id, course_code="DC1CB41", semester="2025_2", attendance_score=7.0, midterm_score=4.0, final_score=2.5, total_score_10=3.2, total_score_4=0.0, grade_letter="F", is_passed=False, status="retake_required"),
                Enrollment(user_id=u_debt.id, course_code="DC2TT23", semester="2025_2", attendance_score=7.5, midterm_score=4.5, final_score=2.8, total_score_10=3.5, total_score_4=0.0, grade_letter="F", is_passed=False, status="retake_required"),
                Enrollment(user_id=u_debt.id, course_code="DC2TT22", semester="2026_1", attendance_score=8.5, midterm_score=7.0, final_score=7.0, total_score_10=7.2, total_score_4=3.0, grade_letter="B", is_passed=True, status="completed"),

                # Sinh vien Frontend Demo 75DCTT12345 (CNTT)
                Enrollment(user_id=u_fe_cntt.id, course_code="DC1CB11", semester="2025_2", attendance_score=9.5, midterm_score=8.0, final_score=8.2, total_score_10=8.3, total_score_4=3.5, grade_letter="B+", is_passed=True, status="completed"),
                Enrollment(user_id=u_fe_cntt.id, course_code="DC1TT44", semester="2025_2", attendance_score=10.0, midterm_score=8.5, final_score=8.5, total_score_10=8.7, total_score_4=3.7, grade_letter="A", is_passed=True, status="completed"),
                Enrollment(user_id=u_fe_cntt.id, course_code="DC2TT23", semester="2026_1", attendance_score=9.0, midterm_score=7.5, final_score=7.8, total_score_10=7.9, total_score_4=3.0, grade_letter="B", is_passed=True, status="completed"),

                # Sinh vien Frontend Demo 74DCOT99881 (Co khi O to - no 1 mon)
                Enrollment(user_id=u_fe_oto.id, course_code="CK2OT11", semester="2025_2", attendance_score=8.5, midterm_score=7.5, final_score=7.5, total_score_10=7.6, total_score_4=3.0, grade_letter="B", is_passed=True, status="completed"),
                Enrollment(user_id=u_fe_oto.id, course_code="CK2OT22", semester="2026_1", attendance_score=7.0, midterm_score=4.0, final_score=3.0, total_score_10=3.6, total_score_4=0.0, grade_letter="F", is_passed=False, status="retake_required"),
            ]
            db.add_all(enrollments_seed)
            db.commit()

        if db.query(Timetable).count() == 0:
            timetable_seed = [
                # 21010001
                Timetable(user_id=u_good.id, course_code="DC3HT12", semester="2026_1", day_of_week=2, day_label="Thứ 2", start_period=1, end_period=3, time_range="07:00 - 09:35", room="P.402 - Nhà A2", lecturer_name="TS. Nguyễn Hoàng Minh", class_group="72DCHT21"),
                Timetable(user_id=u_good.id, course_code="DC3HT21", semester="2026_1", day_of_week=4, day_label="Thứ 4", start_period=4, end_period=6, time_range="09:45 - 12:20", room="Phòng máy 305 - Nhà A1", lecturer_name="ThS. Trần Thu Hà", class_group="72DCHT21"),
                Timetable(user_id=u_good.id, course_code="DC3HT41", semester="2026_1", day_of_week=6, day_label="Thứ 6", start_period=7, end_period=9, time_range="13:00 - 15:35", room="P.501 - Nhà A2", lecturer_name="TS. Lê Quang Huy", class_group="72DCHT21"),

                # 21010002
                Timetable(user_id=u_debt.id, course_code="DC2HT13", semester="2026_1", day_of_week=3, day_label="Thứ 3", start_period=1, end_period=3, time_range="07:00 - 09:35", room="P.304 - Nhà A2", lecturer_name="ThS. Vũ Đình Nam", class_group="72DCHT22"),
                Timetable(user_id=u_debt.id, course_code="DC2HT36", semester="2026_1", day_of_week=5, day_label="Thứ 5", start_period=7, end_period=9, time_range="13:00 - 15:35", room="Phòng máy 201 - Nhà A1", lecturer_name="TS. Phạm Thanh Tùng", class_group="72DCHT22"),

                # 23010003 (Tan sinh vien K75 - chi co TKB tuan dau)
                Timetable(user_id=u_fresh.id, course_code="DC1CB11", semester="2026_1", day_of_week=2, day_label="Thứ 2", start_period=1, end_period=4, time_range="07:00 - 10:30", room="P.202 - Nhà H1", lecturer_name="PGS.TS. Đỗ Văn Hùng", class_group="75DCTT21"),
                Timetable(user_id=u_fresh.id, course_code="DC1TT44", semester="2026_1", day_of_week=4, day_label="Thứ 4", start_period=7, end_period=9, time_range="13:00 - 15:35", room="Phòng máy 102 - Nhà A1", lecturer_name="ThS. Nguyễn Thị Lan", class_group="75DCTT21"),
                Timetable(user_id=u_fresh.id, course_code="DC1TT21", semester="2026_1", day_of_week=6, day_label="Thứ 6", start_period=1, end_period=3, time_range="07:00 - 09:35", room="P.301 - Nhà H1", lecturer_name="TS. Bùi Văn Kiên", class_group="75DCTT21"),

                # 75DCTT12345
                Timetable(user_id=u_fe_cntt.id, course_code="DC2HT26", semester="2026_1", day_of_week=2, day_label="Thứ 2", start_period=4, end_period=6, time_range="09:45 - 12:20", room="P.405 - Nhà A2", lecturer_name="TS. Nguyễn Hoàng Minh", class_group="75DCTT23"),
                Timetable(user_id=u_fe_cntt.id, course_code="DC2TT22", semester="2026_1", day_of_week=5, day_label="Thứ 5", start_period=1, end_period=3, time_range="07:00 - 09:35", room="Phòng máy 302 - Nhà A1", lecturer_name="ThS. Trần Thu Hà", class_group="75DCTT23"),

                # 74DCOT99881
                Timetable(user_id=u_fe_oto.id, course_code="CK3OT15", semester="2026_1", day_of_week=3, day_label="Thứ 3", start_period=7, end_period=9, time_range="13:00 - 15:35", room="Xưởng thực hành Ô tô B1", lecturer_name="TS. Đặng Quốc Việt", class_group="74DCOT21"),
            ]
            db.add_all(timetable_seed)
            db.commit()

        if db.query(Exam).count() == 0:
            exams_seed = [
                # 21010001 (3 mon thi sap toi theo dung Dac ta)
                Exam(user_id=u_good.id, course_code="DC3HT12", semester="2026_1", exam_date=date(2026, 12, 18), exam_time="07:30 - 09:00", room="P.301 - Nhà A2", seat_number="SBD-04", exam_format="Tự luận kết hợp Trắc nghiệm", notes="Mang theo thẻ sinh viên"),
                Exam(user_id=u_good.id, course_code="DC3HT21", semester="2026_1", exam_date=date(2026, 12, 22), exam_time="09:30 - 11:00", room="Phòng máy 305 - Nhà A1", seat_number="M-12", exam_format="Thực hành trên máy tính", notes="Có mặt trước 15 phút"),
                Exam(user_id=u_good.id, course_code="DC3HT41", semester="2026_1", exam_date=date(2026, 12, 26), exam_time="13:30 - 15:00", room="P.402 - Nhà A2", seat_number="SBD-09", exam_format="Vấn đáp tiểu luận", notes="Nộp báo cáo trước ngày thi"),

                # 21010002
                Exam(user_id=u_debt.id, course_code="DC2HT13", semester="2026_1", exam_date=date(2026, 12, 19), exam_time="07:30 - 09:00", room="P.204 - Nhà A2", seat_number="SBD-18", exam_format="Trắc nghiệm trên máy", notes="Mang theo thẻ sinh viên"),
                Exam(user_id=u_debt.id, course_code="DC2HT36", semester="2026_1", exam_date=date(2026, 12, 24), exam_time="13:30 - 15:00", room="Phòng máy 201 - Nhà A1", seat_number="M-07", exam_format="Bảo vệ bài tập lớn", notes="Chuẩn bị source code demo"),

                # 75DCTT12345
                Exam(user_id=u_fe_cntt.id, course_code="DC2HT26", semester="2026_1", exam_date=date(2026, 12, 20), exam_time="07:30 - 09:00", room="P.405 - Nhà A2", seat_number="SBD-11", exam_format="Tự luận", notes="Mang theo thẻ sinh viên"),
                Exam(user_id=u_fe_cntt.id, course_code="DC2TT22", semester="2026_1", exam_date=date(2026, 12, 25), exam_time="09:30 - 11:00", room="Phòng máy 302 - Nhà A1", seat_number="M-15", exam_format="Thực hành SQL", notes="Mang theo thẻ sinh viên"),

                # 74DCOT99881
                Exam(user_id=u_fe_oto.id, course_code="CK3OT15", semester="2026_1", exam_date=date(2026, 12, 21), exam_time="13:30 - 15:00", room="P.105 - Nhà B1", seat_number="SBD-06", exam_format="Tự luận", notes="Mang theo thẻ sinh viên"),
            ]
            db.add_all(exams_seed)
            db.commit()

        print(
            f"[3/4] Đã nạp dữ liệu học vụ: {db.query(Enrollment).count()} bản ghi điểm, "
            f"{db.query(Timetable).count()} lịch học, {db.query(Exam).count()} lịch thi."
        )

        # 4. SYNC 68 OFFICIAL UTT DOCUMENTS TU KHO RAG VAO BANG DOCUMENTS
        if RAG_META_FILE.exists() and db.query(Document).count() == 0:
            with open(RAG_META_FILE, "r", encoding="utf-8") as f:
                chunks_meta = json.load(f)

            grouped = defaultdict(list)
            for item in chunks_meta:
                grouped[item["source"]].append(item)

            raw_files_index = {}
            if RAG_RAW_DIR.exists():
                for fp in RAG_RAW_DIR.rglob("*"):
                    if fp.is_file():
                        raw_files_index[fp.name] = fp

            docs_to_insert = []
            for src_name, items in grouped.items():
                first = items[0]
                fp = raw_files_index.get(src_name)
                f_size = _fmt_bytes(fp.stat().st_size) if fp and fp.exists() else f"{sum(c.get('char_count', 0) for c in items) // 1024 + 1} KB"
                ext = Path(src_name).suffix.lstrip(".").upper() or "PDF"

                docs_to_insert.append(
                    Document(
                        name=src_name,
                        title=first.get("doc_title", src_name),
                        category=first.get("category", "Tài liệu UTT"),
                        department="Trường Đại học Công nghệ GTVT (UTT)",
                        effective_date="2024",
                        source_url="https://utt.edu.vn",
                        size=f_size,
                        type=ext,
                        status="processed",
                        is_active=True,
                        chunk_count=len(items),
                        vector_ids=[c["chunk_id"] for c in items],
                        upload_date=datetime.now(timezone.utc),
                    )
                )
            db.add_all(docs_to_insert)
            db.commit()
            print(f"[4/4] Đã đồng bộ {len(docs_to_insert)} văn bản UTT ({len(chunks_meta):,} vector_ids) vào bảng documents.")
        else:
            print(f"[4/4] Bảng documents hiện có {db.query(Document).count()} văn bản.")

        print("=" * 72)
        print("HOÀN TẤT KHỞI TẠO CƠ SỞ DỮ LIỆU UTEE THÀNH CÔNG!")
        print("=" * 72)
    finally:
        db.close()


if __name__ == "__main__":
    do_reset = "--reset" in sys.argv
    seed_all(reset=do_reset)
