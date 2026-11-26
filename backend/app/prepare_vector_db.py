"""
prepare_vector_db.py - Script khoi tao lai toan bo Pure FAISS Vector Database tu thu muc tai lieu UTT
su dung Google AI Studio Gemini Embedding API (gemini-embedding-001).
Ke thua prepare_vector_db.py cua repo NCKH.
"""

from pathlib import Path

from app.vectorstore import VectorStore, extract_pages_from_file, semantic_chunk_pages

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = BACKEND_DIR.parent / "RAG" / "data" / "raw"
UPLOAD_DATA_DIR = BACKEND_DIR / "app" / "data"


def rebuild_faiss_from_directory(data_dir: Path = DEFAULT_RAW_DIR) -> int:
    if not data_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục tài liệu nguồn: {data_dir}")

    valid_exts = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"}
    files = [
        p for p in data_dir.rglob("*")
        if p.is_file() and not p.name.startswith("~$") and p.suffix.lower() in valid_exts
    ]
    print(f"[PREPARE VECTOR DB] Tìm thấy {len(files)} tài liệu hợp lệ trong {data_dir}")

    all_chunks = []
    for idx, fp in enumerate(files, start=1):
        print(f"  [{idx}/{len(files)}] Trích xuất & băm đoạn: {fp.name}...")
        pages = extract_pages_from_file(fp)
        if not pages:
            continue
        chunks = semantic_chunk_pages(pages, doc_title=fp.stem, category="Tài liệu UTT")
        all_chunks.extend(chunks)

    store = VectorStore.get_instance()
    store.index.reset()
    store.metadata = []
    VectorStore.add_chunks(all_chunks)
    print(f"[PREPARE VECTOR DB] Hoàn tất lưu {len(all_chunks):,} chunks vào FAISS!")
    return len(all_chunks)


if __name__ == "__main__":
    rebuild_faiss_from_directory()
