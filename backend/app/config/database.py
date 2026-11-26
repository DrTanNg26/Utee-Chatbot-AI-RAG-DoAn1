import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env tu thu muc backend hoac thu muc goc repo
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT_ENV = BACKEND_DIR.parent / ".env"
BACKEND_ENV = BACKEND_DIR / ".env"

if REPO_ROOT_ENV.exists():
    load_dotenv(REPO_ROOT_ENV)
if BACKEND_ENV.exists():
    load_dotenv(BACKEND_ENV, override=True)


def _resolve_database_url() -> str:
    raw_url = (os.getenv("DATABASE_URL") or "").strip()
    if not raw_url:
        # Fallback an toan cho moi truong Dev local khi chua bat Docker PostgreSQL
        sqlite_path = BACKEND_DIR / "utee_local.db"
        return f"sqlite:///{sqlite_path.as_posix()}"

    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]

    # Tu dong chon driver PostgreSQL da cai tren may (psycopg2 hoac psycopg v3)
    if raw_url.startswith("postgresql://"):
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            try:
                import psycopg  # noqa: F401
                raw_url = "postgresql+psycopg://" + raw_url[len("postgresql://"):]
            except ImportError:
                pass

    return raw_url


SQLALCHEMY_DATABASE_URL = _resolve_database_url()

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Bat FOREIGN KEY pragma khi chay SQLite de dam bao rang buoc toan ven nhu PostgreSQL
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI Dependency cung cap DB session an toan cho moi request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
