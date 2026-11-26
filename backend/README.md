# UTee AI Companion — Backend API (`Đồ án 1 - UTT`)

Phần **Backend** của hệ thống Chatbot AI đồng hành với sinh viên Trường Đại học Công nghệ Giao thông vận tải (**UTee**), được thiết kế kế thừa kiến trúc từ repo tham khảo `NCKH/chatbot-for-docs-backend` và mở rộng đầy đủ theo **Tài liệu Đặc tả Kỹ thuật UTee**:

* **Web Framework:** Python **FastAPI** + Uvicorn + Pydantic v2.
* **Vector Database (Thuần FAISS):** `faiss-cpu` (`IndexFlatIP` + chuẩn hóa L2 = Cosine Similarity, 768 chiều), tự động đồng bộ kho **2,174 chunks** từ **68 văn bản quy chế & đề cương chính thức của UTT**.
* **AI & Embedding Engine:** **Google AI Studio Gemini API** (`google-genai`: `gemini-2.5-flash` & `gemini-embedding-001`), hỗ trợ xoay vòng nhiều API Key chống Rate Limit `429`.
* **Cơ sở dữ liệu & ORM:** **PostgreSQL 16** (hoặc SQLite cho môi trường dev nhanh) + **SQLAlchemy 2.0** + **Alembic Migrations**.
* **Bảo mật & Phân quyền (RBAC):** JWT (`python-jose` / `PyJWT`) + băm mật khẩu `bcrypt`, chống hỏi chéo dữ liệu cá nhân giữa các sinh viên (`A` không xem được `B`), chặn khách chưa đăng nhập hỏi dữ liệu học vụ, chống Prompt Injection và ghi Nhật ký vận hành (`operation_logs`).

---

## 1. Cấu trúc thư mục `backend/`

```text
backend/
├── app/
│   ├── auth/
│   │   ├── util.py             # JWT, Bcrypt, Dependencies (get_current_user, get_optional_user, get_current_admin)
│   │   ├── security.py         # Chống hỏi chéo tài khoản (RBAC), chống Prompt Injection, ghi OperationLog
│   │   ├── auth_service.py     # Xác thực sinh viên/admin, danh sách tài khoản demo
│   │   └── routers.py          # /auth/* (NCKH) & /api/v1/auth/* (UTee Spec)
│   ├── config/
│   │   ├── cors.py             # Khởi tạo FastAPI + CORS (hỗ trợ Vite 8080/5173 & React/Next 3000)
│   │   └── database.py         # SQLAlchemy Engine, SessionLocal, get_db
│   ├── schemas/                # Pydantic v2 DTOs (auth, chat, student, admin)
│   ├── services/
│   │   ├── chat_service.py     # Chat API, SSE Streaming, Cookie khách (/ck), Lịch sử hội thoại
│   │   ├── student_service.py  # Truy vấn SQL có phân quyền: Hồ sơ, Điểm, Nợ môn, TKB, Lịch thi
│   │   └── admin_service.py    # Upload/Chunk/Embed tài liệu mới vào FAISS, Toggle, Xóa, Signed URL, Stats
│   ├── chatbot_config.json     # Cấu hình động của Bot (Model, Temperature, Top-K, Threshold...)
│   ├── config_manager.py       # Tự động reload chatbot_config.json bằng Watchdog (kế thừa NCKH)
│   ├── memory.py               # PostgresChatMessageHistory + Cửa sổ trượt ngữ cảnh (Sliding Window)
│   ├── models.py               # SQLAlchemy ORM (10 bảng quan hệ chuẩn hóa)
│   ├── prepare_vector_db.py    # Script biên dịch lại FAISS từ thư mục tài liệu gốc
│   ├── qa_engine.py            # Intent Router (GENERAL_RAG / PERSONAL_SQL / HYBRID_SQL_RAG) + Gemini LLM
│   ├── routes.py               # Admin Routers (/admin/* & /api/v1/admin/*)
│   ├── vectorstore.py          # Singleton Pure FAISS VectorStore + Google Gemini Embedding
│   └── main.py                 # Điểm khởi chạy FastAPI
├── alembic/                    # Quản lý phiên bản schema CSDL bằng Alembic
├── tests/
│   └── test_backend_suite.py   # Bộ kiểm thử tự động toàn diện (Auth, RBAC, RAG, Hybrid, Security, Admin)
├── docker-compose.yml          # Khởi chạy nhanh PostgreSQL 16 chỉ với 1 lệnh
├── Dockerfile                  # Đóng gói container Backend
├── schema.sql                  # Script DDL PostgreSQL & truy vấn nghiệp vụ mẫu
├── seed_db.py                  # Script dựng lại CSDL & nạp 6 tài khoản kịch bản Demo + 68 văn bản UTT
├── system_prompt_v1.md         # Tài liệu quản lý phiên bản System Prompt
├── .env.example                # Cấu hình biến môi trường mẫu (không chứa secret thật)
└── requirements.txt            # Danh sách thư viện Python
```

---

## 2. Hướng dẫn Cài đặt & Chạy nhanh

### Bước 1: Cài đặt thư viện
```bash
cd backend
pip install -r requirements.txt
```

### Bước 2: Cấu hình biến môi trường `.env`
Copy file `.env.example` thành `.env` và điền **Google AI Studio API Key** (`GEMINI_API_KEY`):
```bash
copy .env.example .env
```
* **Nếu dùng PostgreSQL (Khuyên dùng khi Demo chính thức):**
  ```bash
  docker compose up -d
  ```
  Giữ `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/utee_db` trong `.env`.
* **Nếu chạy thử nhanh trên máy chưa bật Docker:** Có thể đặt `DATABASE_URL=sqlite:///./utee_local.db` (hoặc để trống `DATABASE_URL`).

### Bước 3: Khởi tạo CSDL & Dữ liệu giả lập Demo
```bash
alembic upgrade head
python seed_db.py --reset
```

### Bước 4: Khởi động Backend Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
* **Swagger UI (Tài liệu & Test API trực quan):** http://localhost:8000/docs

---

## 3. Danh sách Tài khoản Kịch bản Demo (Mật khẩu chung: `utt123456`)

| Tài khoản (`username`) | Họ tên | Vai trò | Kịch bản kiểm thử & Demo |
| :--- | :--- | :--- | :--- |
| `21010001` | Nguyễn Văn A | `student` | **SV Giỏi** (CNTT, K72, 70 TC, GPA `3.45`, không nợ môn, đủ TKB & 3 môn thi) |
| `21010002` | Trần Thị B | `student` | **SV Nợ môn** (Nợ 2 môn điểm `F`: *Toán cao cấp 2* & *Lập trình C++* $\rightarrow$ Demo **Hybrid SQL + RAG**) |
| `23010003` | Lê Văn C | `student` | **SV Khóa mới Năm 1** (K75, chưa có điểm tổng kết, có TKB tuần đầu) |
| `75DCTT12345` | Phạm Minh Đức | `student` | Khớp trực tiếp nút **Demo CNTT** trên giao diện Frontend hiện tại (`c:\Doan1\frontend`) |
| `74DCOT99881` | Hoàng Quốc Bảo | `student` | Khớp trực tiếp nút **Demo Cơ khí Ô tô** trên giao diện Frontend hiện tại (`c:\Doan1\frontend`) |
| `admin_demo` (`admin@utt.edu.vn`) | Quản trị viên UTT | `admin` | Upload tài liệu RAG mới, bật/tắt văn bản cũ, xem thống kê & Nhật ký bảo mật |

---

## 4. Chạy bộ kiểm thử tự động
```bash
python tests/test_backend_suite.py
```
