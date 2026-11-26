-- ============================================================================
-- SCHEMA CO SO DU LIEU QUAN HE - HE THONG CHATBOT AI UTEE (DO AN 1 - UTT)
-- He quan tri CSDL: PostgreSQL 16 (Thuan quan he; Vector RAG luu tren FAISS)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Bang users: Quan ly tai khoan dang nhap va phan vai (RBAC)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) NOT NULL UNIQUE,           -- MSSV (vd: 21010001, 75DCTT12345) hoac username admin
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255),                     -- Mat khau bam Bcrypt (NULL neu la guest cookie tam)
    full_name VARCHAR(120),
    role VARCHAR(20) NOT NULL DEFAULT 'student'
        CHECK (role IN ('guest', 'student', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 2. Bang students: Ho so ca nhan va hoc vu sinh vien (Quan he 1-1 voi users)
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    student_code VARCHAR(32) NOT NULL UNIQUE,       -- Ma sinh vien dinh danh
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    faculty VARCHAR(150) NOT NULL,                  -- Khoa (vd: Khoa Cong nghe Thong tin - UTT)
    major_name VARCHAR(150) NOT NULL,               -- Nganh hoc (vd: Cong nghe thong tin)
    class_name VARCHAR(50) NOT NULL,                -- Lop sinh hoat (vd: 72DCHT21)
    cohort VARCHAR(20) NOT NULL,                    -- Khoa hoc (vd: K72, K75)
    total_credits_earned INTEGER NOT NULL DEFAULT 0 CHECK (total_credits_earned >= 0),
    program_total_credits INTEGER NOT NULL DEFAULT 150 CHECK (program_total_credits > 0),
    current_gpa_4 NUMERIC(3, 2) DEFAULT 0.00 CHECK (current_gpa_4 >= 0.00 AND current_gpa_4 <= 4.00),
    current_gpa_10 NUMERIC(4, 2) DEFAULT 0.00 CHECK (current_gpa_10 >= 0.00 AND current_gpa_10 <= 10.00),
    training_score INTEGER DEFAULT 80 CHECK (training_score >= 0 AND training_score <= 100),
    academic_status VARCHAR(50) NOT NULL DEFAULT 'Bình thường'
);

CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id);

-- 3. Bang courses: Danh muc hoc phan dao tao
CREATE TABLE IF NOT EXISTS courses (
    course_code VARCHAR(32) PRIMARY KEY,            -- Ma hoc phan (vd: DC1CB11, DC1CB41, DC2TT23)
    course_name VARCHAR(200) NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0),
    major_name VARCHAR(150) NOT NULL DEFAULT 'Công nghệ thông tin',
    semester_recommended INTEGER CHECK (semester_recommended >= 1 AND semester_recommended <= 10),
    prerequisite_code VARCHAR(32) REFERENCES courses(course_code) ON DELETE SET NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE
);

-- 4. Bang enrollments: Ket qua hoc tap va trang thai mon hoc (Bang diem / Mon hoc lai)
CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_code VARCHAR(32) NOT NULL REFERENCES courses(course_code) ON DELETE CASCADE,
    semester VARCHAR(20) NOT NULL,                  -- Ky hoc (vd: 2025_1, 2025_2, 2026_1)
    attendance_score NUMERIC(4, 2) CHECK (attendance_score >= 0 AND attendance_score <= 10),
    midterm_score NUMERIC(4, 2) CHECK (midterm_score >= 0 AND midterm_score <= 10),
    final_score NUMERIC(4, 2) CHECK (final_score >= 0 AND final_score <= 10),
    total_score_10 NUMERIC(4, 2) CHECK (total_score_10 >= 0 AND total_score_10 <= 10),
    total_score_4 NUMERIC(3, 2) CHECK (total_score_4 >= 0 AND total_score_4 <= 4),
    grade_letter VARCHAR(5) CHECK (grade_letter IN ('A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F', 'P', 'IP')),
    is_passed BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'completed' -- completed | studying | retake_required
        CHECK (status IN ('completed', 'studying', 'retake_required')),
    CONSTRAINT uq_enrollment_user_course_sem UNIQUE (user_id, course_code, semester)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_user_id ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_passed ON enrollments(user_id, is_passed);

-- 5. Bang timetable: Thoi khoa bieu tuan cua sinh vien
CREATE TABLE IF NOT EXISTS timetable (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_code VARCHAR(32) NOT NULL REFERENCES courses(course_code) ON DELETE CASCADE,
    semester VARCHAR(20) NOT NULL,
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 2 AND day_of_week <= 8), -- 2=Thu 2 ... 8=Chu nhat
    day_label VARCHAR(20) NOT NULL,                 -- "Thứ 2" .. "Chủ nhật"
    start_period INTEGER NOT NULL CHECK (start_period >= 1 AND start_period <= 15),
    end_period INTEGER NOT NULL CHECK (end_period >= start_period AND end_period <= 16),
    time_range VARCHAR(40) NOT NULL,                -- vd: "07:00 - 09:35"
    room VARCHAR(50) NOT NULL,                      -- vd: "P.402 - Nhà A2 (Cơ sở Hà Nội)"
    lecturer_name VARCHAR(120) NOT NULL,
    class_group VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_timetable_user_day ON timetable(user_id, day_of_week);

-- 6. Bang exams: Lich thi ket thuc hoc phan
CREATE TABLE IF NOT EXISTS exams (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_code VARCHAR(32) NOT NULL REFERENCES courses(course_code) ON DELETE CASCADE,
    semester VARCHAR(20) NOT NULL,
    exam_date DATE NOT NULL,
    exam_time VARCHAR(40) NOT NULL,                 -- vd: "07:30 - 09:00"
    room VARCHAR(50) NOT NULL,                      -- vd: "P.305 - Nhà H1"
    seat_number VARCHAR(15),
    exam_format VARCHAR(60) NOT NULL,               -- Tự luận | Trắc nghiệm trên máy | Vấn đáp
    notes VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_exams_user_date ON exams(user_id, exam_date);

-- 7. Bang documents: Quan ly metadata tai lieu RAG (Ke thua NCKH + Lien ket vector_ids FAISS)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,              -- Ten file luu tru
    title VARCHAR(255) NOT NULL,                    -- Ten hien thi van ban quy che
    category VARCHAR(100) NOT NULL DEFAULT 'Tài liệu UTT',
    department VARCHAR(150) DEFAULT 'Phòng Đào tạo UTT',
    effective_date VARCHAR(30),
    source_url VARCHAR(500),
    size VARCHAR(40) NOT NULL DEFAULT '0 KB',
    type VARCHAR(20) NOT NULL DEFAULT 'PDF',        -- PDF | DOCX | XLSX | TXT | MD
    status VARCHAR(30) NOT NULL DEFAULT 'processed' -- processed | pending | failed | disabled
        CHECK (status IN ('processed', 'pending', 'failed', 'disabled')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,        -- Cho phep Admin tat/bat tai lieu cu tren RAG
    chunk_count INTEGER NOT NULL DEFAULT 0,
    vector_ids JSONB,                               -- Danh sach chunk_id trong FAISS (ke thua NCKH)
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Bang conversations: Quan ly danh sach cac cuoc tro chuyen
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'Cuộc trò chuyện mới',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);

-- 9. Bang messages: Luu chi tiet tin nhan, nguon trich dan RAG va the du lieu (Rich Cards)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'assistant', 'system')),
    message TEXT NOT NULL,
    intent VARCHAR(40),                             -- GENERAL_RAG | PERSONAL_SQL | HYBRID_SQL_RAG | GREETING_QUICK
    sources JSONB,                                  -- Danh sach citations tu FAISS
    structured_data JSONB,                          -- Du lieu Rich Cards (grades/timetable/exams/retake)
    latency_ms NUMERIC(10, 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at);

-- 10. Bang operation_logs: Nhat ky van hanh & canh bao bao mat (RBAC / Prompt Injection)
CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(64),
    event_type VARCHAR(50) NOT NULL,                -- CHAT_QUERY | AUTH_DENIED | CROSS_ACCOUNT_DENIED | PROMPT_INJECTION_BLOCKED | DOC_UPLOAD | DOC_DELETE
    intent VARCHAR(40),
    query_preview VARCHAR(300),                     -- Khong luu du lieu nhay cam / diem chi tiet vao log
    status_code INTEGER NOT NULL DEFAULT 200,
    latency_ms NUMERIC(10, 1),
    detail VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oplogs_created ON operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_oplogs_event ON operation_logs(event_type);

-- ============================================================================
-- TRUY VAN NGHIEP VU MAU (KIEM CHUNG TUAN 2 & BAO VE DO AN)
-- ============================================================================

-- Truy van 1: Lay danh sach cac hoc phan chua dat (Diem F / can hoc lai) cua 1 sinh vien xac thuc
-- SELECT c.course_code, c.course_name, c.credits, e.semester, e.total_score_10, e.grade_letter
-- FROM enrollments e
-- JOIN courses c ON e.course_code = c.course_code
-- WHERE e.user_id = :authenticated_user_id AND e.is_passed = FALSE
-- ORDER BY e.semester DESC;

-- Truy van 2: Lay thoi khoa bieu trong tuan cua sinh vien sap xep theo Thu va Tiet bat dau
-- SELECT t.day_label, t.start_period, t.end_period, t.time_range, c.course_name, t.room, t.lecturer_name
-- FROM timetable t
-- JOIN courses c ON t.course_code = c.course_code
-- WHERE t.user_id = :authenticated_user_id
-- ORDER BY t.day_of_week ASC, t.start_period ASC;

-- Truy van 3: Thong ke tong hop tien do hoc tap & so mon no cua tung sinh vien demo
-- SELECT s.student_code, u.full_name, s.major_name, s.total_credits_earned, s.current_gpa_4,
--        COUNT(CASE WHEN e.is_passed = FALSE THEN 1 END) AS failed_courses_count
-- FROM students s
-- JOIN users u ON s.user_id = u.id
-- LEFT JOIN enrollments e ON u.id = e.user_id
-- GROUP BY s.student_code, u.full_name, s.major_name, s.total_credits_earned, s.current_gpa_4;
