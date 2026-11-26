"""
vectorstore.py - Singleton quan ly Pure FAISS Vector Database + Google Gemini Studio API.
Ke thua kien truc VectorStore cua repo NCKH (get_instance, save, add_texts, delete)
va ket hop truc tiep voi kho 2,174 chunks quy che UTT (gemini-embedding-001, 768D).
"""

import json
import os
from pathlib import Path
import re
import shutil
import time
import unicodedata
from typing import Any, Dict, List, Optional, Set
import uuid

import docx
from dotenv import load_dotenv
import faiss
from google import genai
from google.genai import types
import numpy as np
import openpyxl
from pypdf import PdfReader

from app.config_manager import load_config

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    text = re.sub(r"[ \t\u00a0\u200b]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_pages_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """Trich xuat van ban kem so trang/sheet tu PDF, DOCX, XLSX, TXT, MD."""
    ext = file_path.suffix.lower()
    items: List[Dict[str, Any]] = []

    if ext == ".pdf":
        reader = PdfReader(str(file_path))
        for idx, page in enumerate(reader.pages, start=1):
            txt = _clean_text(page.extract_text() or "")
            if len(txt) >= 15:
                items.append({"source": file_path.name, "page": idx, "text": txt})

    elif ext == ".docx":
        doc = docx.Document(str(file_path))
        paragraphs = [_clean_text(p.text) for p in doc.paragraphs if _clean_text(p.text)]
        tables_md = []
        for tbl in doc.tables:
            rows = []
            for r in tbl.rows:
                dedup = []
                for cell in r.cells:
                    c_txt = _clean_text(cell.text)
                    if not dedup or c_txt != dedup[-1]:
                        dedup.append(c_txt)
                if any(dedup):
                    rows.append(" | ".join(dedup))
            if rows:
                tables_md.append("[BẢNG BIỂU]:\n" + "\n".join(rows))
        combined = "\n\n".join(paragraphs + tables_md).strip()
        if combined:
            items.append({"source": file_path.name, "page": 1, "text": combined})

    elif ext in (".xlsx", ".xls"):
        wb = openpyxl.load_workbook(str(file_path), data_only=True)
        for s_name in wb.sheetnames:
            sheet = wb[s_name]
            lines = [f"[SHEET: {s_name}]"]
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    lines.append(" | ".join(cells))
            if len(lines) > 1:
                items.append({"source": file_path.name, "page": s_name, "text": _clean_text("\n".join(lines))})

    elif ext in (".txt", ".md"):
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        cleaned = _clean_text(raw)
        if cleaned:
            items.append({"source": file_path.name, "page": 1, "text": cleaned})

    return items


def semantic_chunk_pages(
    pages: List[Dict[str, Any]],
    doc_title: str,
    category: str = "Tài liệu UTT",
    doc_id: Optional[int] = None,
    max_chars: int = 1000,
    overlap_chars: int = 150,
) -> List[Dict[str, Any]]:
    """Bam van ban theo cau truc CHUONG / Dieu / Khoan (600-800 tokens ~ 1000 ky tu)."""
    if not pages:
        return []

    source_file = pages[0]["source"]
    full_text = ""
    page_offsets: List[tuple[int, Any]] = []
    for p in pages:
        page_offsets.append((len(full_text), p.get("page", 1)))
        full_text += p["text"] + "\n\n"

    pattern = r"(?=(?:^|\n)(?:CHƯƠNG\s+[IVXLCDM\d]+[^\n]*|Điều\s+\d+[\.:\s][^\n]*|[IVXLCDM]+\.\s+[A-ZÀ-ỸĐ][^\n]*))"
    parts = [pt.strip() for pt in re.split(pattern, full_text, flags=re.MULTILINE) if pt.strip()]

    chunks: List[Dict[str, Any]] = []
    current_chapter = ""
    running_pos = 0
    chunk_seq = 1

    for part in parts:
        first_line = part.split("\n")[0].strip()
        if re.match(r"^CHƯƠNG\s+[IVXLCDM\d]+", first_line, flags=re.IGNORECASE):
            current_chapter = first_line
            sec_title = first_line
        elif re.match(r"^Điều\s+\d+", first_line, flags=re.IGNORECASE):
            sec_title = f"{current_chapter} - {first_line}" if current_chapter else first_line
        else:
            sec_title = first_line[:90]

        matched_page: Any = 1
        for offset, pg in page_offsets:
            if running_pos >= offset:
                matched_page = pg
            else:
                break
        running_pos += len(part)

        # Cat nho neu dieu khoan vuot qua max_chars
        sub_texts: List[str] = []
        if len(part) <= max_chars:
            sub_texts = [part]
        else:
            step = max(max_chars - overlap_chars, 200)
            for idx in range(0, len(part), step):
                piece = part[idx : idx + max_chars].strip()
                if piece:
                    sub_texts.append(piece)

        for sub_idx, sub_txt in enumerate(sub_texts, start=1):
            disp_sec = f"{sec_title} (Phần {sub_idx}/{len(sub_texts)})" if len(sub_texts) > 1 else sec_title
            enriched = f"[{doc_title}] - {disp_sec}\n{sub_txt}"
            cid = f"{Path(source_file).stem}_{uuid.uuid4().hex[:8]}_c{chunk_seq:03d}"
            chunks.append(
                {
                    "chunk_id": cid,
                    "doc_id": doc_id,
                    "source": source_file,
                    "doc_title": doc_title,
                    "category": category,
                    "section": disp_sec,
                    "page": matched_page,
                    "content": enriched,
                    "char_count": len(enriched),
                    "token_estimate": len(enriched) // 4,
                }
            )
            chunk_seq += 1

    return chunks


class VectorStore:
    """
    Singleton quan ly Pure FAISS Index (IndexFlatIP + L2 Normalization = Cosine Similarity)
    su dung Google AI Studio Gemini Embedding API (gemini-embedding-001, 768 chieu).
    """

    _instance: Optional["VectorStore"] = None
    _db_path: Path = BACKEND_DIR / "app" / "vectorstores" / "db_faiss"
    _precompiled_rag_dir: Path = REPO_ROOT / "RAG" / "data" / "vectorstore"

    def __init__(self):
        cfg = load_config()
        self.dimension: int = int(cfg.get("embeddingDimension", 768))
        self.embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL") or cfg.get("embeddingModel", "gemini-embedding-001")
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        self.metadata: List[Dict[str, Any]] = []
        self.api_keys: List[str] = []
        self.clients: List[genai.Client] = []
        self.key_cooldowns: List[float] = []
        self.current_client_idx: int = 0

        self._refresh_gemini_clients()
        self._load_or_initialize()

    @classmethod
    def get_instance(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _refresh_gemini_clients(self) -> None:
        """Nap danh sach GEMINI_API_KEY tu .env (ho tro xoay vong nhieu key)."""
        repo_env = REPO_ROOT / ".env"
        backend_env = BACKEND_DIR / ".env"
        if repo_env.exists():
            load_dotenv(repo_env)
        if backend_env.exists():
            load_dotenv(backend_env, override=True)

        keys: List[str] = []
        for k_name in [
            "GEMINI_API_KEY",
            "GEMINI_API_KEY2",
            "GEMINI_API_KEY3",
            "GEMINI_API_KEY4",
            "GEMINI_API_KEY5",
        ]:
            val = os.getenv(k_name, "").strip()
            if val and not val.startswith("your_") and val not in keys:
                keys.append(val)

        if keys and keys != self.api_keys:
            self.api_keys = keys
            self.clients = [genai.Client(api_key=k) for k in keys]
            self.key_cooldowns = [0.0 for _ in keys]
            self.current_client_idx = 0
            print(f"[FAISS VECTORSTORE] Đã kết nối {len(self.clients)} Gemini Studio API Key ({self.embedding_model}).")

    def _get_client(self) -> genai.Client:
        self._refresh_gemini_clients()
        if not self.clients:
            raise RuntimeError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env!")

        now = time.time()
        for _ in range(len(self.clients)):
            idx = self.current_client_idx
            self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
            if now >= self.key_cooldowns[idx]:
                return self.clients[idx]

        # Neu tat ca key dang cooldown ngan, lay key tiep theo
        idx = self.current_client_idx
        self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
        return self.clients[idx]

    def _load_or_initialize(self) -> None:
        """
        1. Uu tien load FAISS index tai backend/app/vectorstores/db_faiss/.
        2. Neu chua co, tu dong ke thua kho 2,174 vectors Gemini da bien dich san trong RAG/data/vectorstore/!
        3. Neu van chua co, khoi tao FAISS IndexFlatIP rong.
        """
        self._db_path.mkdir(parents=True, exist_ok=True)
        index_file = self._db_path / "index.faiss"
        meta_file = self._db_path / "chunks_metadata.json"

        # Bootstrap tu kho RAG/data/vectorstore/faiss_index.bin neu lan dau khoi chay Backend
        if not index_file.exists() or not meta_file.exists():
            src_idx = self._precompiled_rag_dir / "faiss_index.bin"
            src_meta = self._precompiled_rag_dir / "chunks_metadata.json"
            if src_idx.exists() and src_meta.exists():
                shutil.copy2(src_idx, index_file)
                shutil.copy2(src_meta, meta_file)
                print("[FAISS VECTORSTORE] Đã đồng bộ kho 2,174 vectors UTT (Gemini 768D) từ RAG/data/vectorstore!")

        if index_file.exists() and meta_file.exists():
            raw_bytes = np.frombuffer(index_file.read_bytes(), dtype=np.uint8)
            loaded_idx = faiss.deserialize_index(raw_bytes)
            self.index = loaded_idx
            self.dimension = loaded_idx.d
            with open(meta_file, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            print(f"[FAISS VECTORSTORE] Đã nạp {self.index.ntotal:,} vectors ({self.dimension}D) sẵn sàng truy xuất.")
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            print(f"[FAISS VECTORSTORE] Đã tạo mới FAISS IndexFlatIP rỗng ({self.dimension}D).")

    @classmethod
    def save(cls) -> None:
        inst = cls.get_instance()
        inst._db_path.mkdir(parents=True, exist_ok=True)
        index_file = inst._db_path / "index.faiss"
        meta_file = inst._db_path / "chunks_metadata.json"

        serialized = faiss.serialize_index(inst.index).tobytes()
        index_file.write_bytes(serialized)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(inst.metadata, f, ensure_ascii=False, indent=2)
        print(f"[FAISS VECTORSTORE] Đã lưu {inst.index.ntotal:,} vectors vào {index_file}.")

    def embed_texts(self, texts: List[str], batch_size: int = 20) -> np.ndarray:
        """Tao vector embedding qua Google Gemini Studio API va chuan hoa L2."""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        self._refresh_gemini_clients()
        if not self.clients:
            raise RuntimeError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env!")

        all_vecs: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            last_err: Optional[Exception] = None
            for attempt in range(max(len(self.clients) * 2, 2)):
                try:
                    client = self._get_client()
                    resp = client.models.embed_content(
                        model=self.embedding_model,
                        contents=batch,
                        config=types.EmbedContentConfig(output_dimensionality=self.dimension),
                    )
                    all_vecs.extend([emb.values for emb in resp.embeddings])
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    time.sleep(1.5)
            if last_err is not None:
                raise RuntimeError(f"Lỗi gọi Gemini Embedding API: {last_err}")

        arr = np.array(all_vecs, dtype=np.float32)
        faiss.normalize_L2(arr)
        return arr

    @classmethod
    def add_chunks(cls, chunks: List[Dict[str, Any]]) -> List[str]:
        """Nhung danh sach chunk moi bang Gemini API va them vao Pure FAISS Index."""
        if not chunks:
            return []
        inst = cls.get_instance()
        texts = [c["content"] for c in chunks]
        vectors = inst.embed_texts(texts)

        inst.index.add(vectors)
        inst.metadata.extend(chunks)
        cls.save()
        return [c["chunk_id"] for c in chunks]

    @classmethod
    def add_texts(cls, texts: List[str], metadatas: Optional[List[dict]] = None) -> List[str]:
        """Phuong thuc tuong thich truc tiep voi VectorStore.add_texts() cua repo NCKH."""
        if not texts:
            return []
        chunks = []
        for idx, txt in enumerate(texts):
            meta = dict(metadatas[idx]) if metadatas and idx < len(metadatas) else {}
            cid = meta.get("chunk_id") or str(uuid.uuid4())
            chunks.append(
                {
                    "chunk_id": cid,
                    "doc_id": meta.get("doc_id"),
                    "source": meta.get("source", "uploaded_text.txt"),
                    "doc_title": meta.get("doc_title") or meta.get("source", "Tài liệu bổ sung"),
                    "category": meta.get("category", "Tài liệu UTT"),
                    "section": meta.get("section", f"Đoạn {idx + 1}"),
                    "page": meta.get("page", 1),
                    "content": txt,
                    "char_count": len(txt),
                    "token_estimate": len(txt) // 4,
                }
            )
        return cls.add_chunks(chunks)

    @classmethod
    def delete(cls, vector_ids: List[str], source_filename: Optional[str] = None) -> int:
        """
        Xoa chinh xac cac vectors theo danh sach chunk_id (vector_ids luu trong Postgres JSONB)
        bang reconstruct_n tren Pure FAISS IndexFlatIP (khong ton bat ky API call nao!).
        """
        inst = cls.get_instance()
        if inst.index.ntotal == 0 or not inst.metadata:
            return 0

        ids_set = set(str(v) for v in (vector_ids or []))
        keep_positions: List[int] = []
        new_metadata: List[Dict[str, Any]] = []

        for pos, item in enumerate(inst.metadata):
            cid = str(item.get("chunk_id", ""))
            src = item.get("source", "")
            should_remove = (cid in ids_set) or (source_filename and src == source_filename and not ids_set)
            if not should_remove:
                keep_positions.append(pos)
                new_metadata.append(item)

        removed_count = len(inst.metadata) - len(new_metadata)
        if removed_count <= 0:
            return 0

        all_vectors = inst.index.reconstruct_n(0, inst.index.ntotal)
        new_index = faiss.IndexFlatIP(inst.dimension)
        if keep_positions:
            kept_vectors = np.ascontiguousarray(all_vectors[keep_positions], dtype=np.float32)
            new_index.add(kept_vectors)

        inst.index = new_index
        inst.metadata = new_metadata
        cls.save()
        print(f"[FAISS VECTORSTORE] Đã xóa {removed_count} vectors khỏi FAISS.")
        return removed_count

    def _lexical_fallback_search(
        self,
        query: str,
        top_k: int,
        disabled_sources: Set[str],
    ) -> Dict[str, Any]:
        """
        Fallback an toan khi chua dien GEMINI_API_KEY hoac mat mang tam thoi:
        Duyet tu khoa + cum 2 tu tren 2,174 chunks metadata de he thong khong bao gio crash 500.
        """
        q_lower = _clean_text(query).lower()
        stopwords = {
            "là", "gì", "có", "bao", "nhiêu", "như", "thế", "nào", "của", "trường",
            "cho", "hỏi", "về", "thì", "phải", "làm", "được", "trong", "các", "những",
            "với", "theo", "quy", "định", "môn", "học", "phần", "sinh", "viên", "utt",
            "cậu", "tớ", "mình", "bạn", "ơi", "nha", "nhé",
        }
        tokens = [
            t for t in re.split(r"[^\wà-ỹđ]+", q_lower)
            if (len(t) >= 2 or t.isdigit()) and t not in stopwords
        ]
        if not tokens:
            return {"is_grounded": False, "chunks": [], "mode": "lexical_fallback"}

        words = [w for w in re.split(r"[^\wà-ỹđ]+", q_lower) if w]
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]

        scored = []
        for item in self.metadata:
            if item.get("source") in disabled_sources:
                continue
            content_low = item.get("content", "").lower()
            title_low = item.get("doc_title", "").lower()
            sec_low = item.get("section", "").lower()

            token_hits = sum(1 for t in tokens if t in content_low or t in title_low)
            if token_hits == 0:
                continue
            ratio = token_hits / len(tokens)
            bg_hits = sum(
                1 for bg in bigrams
                if len(bg) >= 4 and (bg in title_low or bg in sec_low or bg in content_low)
            )
            score = min(0.45 * ratio + 0.16 * bg_hits, 0.95)
            if ratio >= 0.5 and score >= 0.42:
                copy_item = dict(item)
                copy_item["similarity_score"] = round(score, 4)
                scored.append(copy_item)

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        selected = scored[:top_k]
        return {
            "is_grounded": len(selected) > 0,
            "chunks": selected,
            "mode": "lexical_fallback",
        }

    def search(
        self,
        query: str,
        top_k: int = 4,
        threshold: Optional[float] = None,
        disabled_sources: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Truy van Cosine Similarity tren Pure FAISS (IndexFlatIP) + Lexical Rerank UTT.
        Tu dong bo qua cac tai lieu bi Admin vo hieu hoa (disabled_sources).
        """
        cfg = load_config()
        sim_threshold = threshold if threshold is not None else float(cfg.get("similarityThreshold", 0.56))
        disabled = disabled_sources or set()

        if self.index.ntotal == 0 or not self.metadata:
            return {"is_grounded": False, "chunks": [], "mode": "empty_index"}

        try:
            q_vec = self.embed_texts([query], batch_size=1)
        except Exception as embed_err:
            print(f"[FAISS VECTORSTORE] Fallback tìm kiếm từ khóa do lỗi Gemini Embedding: {embed_err}")
            return self._lexical_fallback_search(query, top_k=top_k, disabled_sources=disabled)

        candidate_k = min(len(self.metadata), max(top_k * 25, 120))
        scores, indices = self.index.search(q_vec, candidate_k)

        q_lower = _clean_text(query).lower()
        stopwords = {
            "là", "gì", "có", "bao", "nhiêu", "như", "thế", "nào", "của", "trường",
            "cho", "hỏi", "về", "thì", "phải", "làm", "được", "trong", "các", "những",
            "với", "theo", "quy", "định", "môn", "học", "phần", "sinh", "viên",
        }
        q_tokens = [
            t for t in re.split(r"[^\wà-ỹđ]+", q_lower)
            if (len(t) >= 2 or t.isdigit()) and t not in stopwords
        ]
        all_words = [w for w in re.split(r"[^\wà-ỹđ]+", q_lower) if w]

        candidates: List[Dict[str, Any]] = []
        for raw_score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = self.metadata[idx]
            if item.get("source") in disabled:
                continue

            base_score = float(raw_score)
            if base_score < sim_threshold * 0.68:
                continue

            content_low = item.get("content", "").lower()
            title_low = item.get("doc_title", "").lower()

            boost = 0.0
            if q_tokens:
                matched_t = sum(1 for t in q_tokens if t in content_low or t in title_low)
                boost += 0.10 * (matched_t / len(q_tokens))

            matched_bg = 0
            for i in range(len(all_words) - 1):
                bg = f"{all_words[i]} {all_words[i + 1]}"
                if len(bg) >= 4 and bg not in ("môn toán", "có bao", "bao nhiêu", "là gì", "thế nào", "điều kiện"):
                    if bg in title_low or f"tên học phần: {bg}" in content_low or bg in content_low[:350]:
                        matched_bg += 1
            boost += min(matched_bg * 0.14, 0.28)

            if "tín" in q_lower and ("số tín chỉ:" in content_low or "thông tin chung về học phần" in content_low):
                boost += 0.12

            final_score = min(base_score + boost, 0.9999)
            if final_score >= sim_threshold:
                copied = dict(item)
                copied["similarity_score"] = round(final_score, 4)
                candidates.append(copied)

        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Dam bao da dang nguon tai lieu
        results: List[Dict[str, Any]] = []
        src_counts: Dict[str, int] = {}
        max_per_src = 1 if ("," in q_lower or " và " in q_lower) else 2
        for c in candidates:
            s = c.get("source", "")
            if src_counts.get(s, 0) >= max_per_src:
                continue
            results.append(c)
            src_counts[s] = src_counts.get(s, 0) + 1
            if len(results) >= top_k:
                break

        if len(results) < top_k:
            for c in candidates:
                if c not in results:
                    results.append(c)
                    if len(results) >= top_k:
                        break

        return {
            "is_grounded": len(results) > 0,
            "chunks": results,
            "mode": f"faiss_gemini/{self.embedding_model}",
        }
