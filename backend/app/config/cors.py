import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="UTee AI Companion Backend API",
    description=(
        "Backend API cho hệ thống Chatbot AI đồng hành cùng sinh viên UTT (Đồ án 1). "
        "Kế thừa kiến trúc NCKH Backend, sử dụng thuần FAISS + Google Gemini Studio API + RBAC SQL."
    ),
    version="1.0.0",
)

default_origins = [
    "http://localhost:8080",      # Vite React Frontend (c:\Doan1\frontend)
    "http://127.0.0.1:8080",
    "http://localhost:5173",      # Vite default port
    "http://127.0.0.1:5173",
    "http://localhost:3000",      # Next.js / CRA port (NCKH frontend)
    "http://127.0.0.1:3000",
]

env_origins = os.getenv("CORS_ORIGINS", "")
if env_origins.strip():
    origins = list(dict.fromkeys([o.strip() for o in env_origins.split(",") if o.strip()] + default_origins))
else:
    origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
