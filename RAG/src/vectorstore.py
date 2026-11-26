"""
vectorstore.py - Module quan ly Vector Database bang FAISS va Google Gemini Embedding.
Ho tro Key Rotation (xoay tua nhieu API Key), Checkpoint tien do, va khac phuc loi Unicode Path tren Windows.
Hoc phan: Do an 1 - He thong Chatbot AI UTee
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Dam bao in tieng Viet an toan tren terminal Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class UteeVectorStore:
    """
    Quan ly Vector Database dung FAISS:
    - Embedding qua Google Gemini voi co che xoay tua nhieu API Key (Key Pool).
    - Tinh toan do tuong dong Cosine Similarity bang IndexFlatIP + L2 normalization.
    - Su dung serialize/deserialize de tuong thich 100% voi duong dan Unicode tren Windows.
    - Luu giu vinh vien cache vectors de khong bao gio phai embed lai khi da hoan tat.
    """
    
    def __init__(self, embedding_model: str = "gemini-embedding-001", dimension: int = 768):
        self.embedding_model = embedding_model
        self.dimension = dimension
        
        # Load tat ca API key co trong file .env (ho tro toi da 5 keys)
        load_dotenv()
        self.api_keys = []
        for key_name in ["GEMINI_API_KEY4", "GEMINI_API_KEY5", "GEMINI_API_KEY6", "GEMINI_API_KEY7", "GEMINI_API_KEY8", "GEMINI_API_KEY9", "GEMINI_API_KEY10"]:
            val = os.getenv(key_name)
            if val and val.strip() and val.strip() not in self.api_keys:
                self.api_keys.append(val.strip())
                
        if not self.api_keys:
            raise ValueError("Khong tim thay bat ky GEMINI_API_KEY nao trong file .env!")
            
        print(f"[KEY POOL] Khoi tao thanh cong {len(self.api_keys)} API Key de xoay tua tang toc do.")
        self.clients = [genai.Client(api_key=k) for k in self.api_keys]
        self.key_cooldowns = [0.0 for _ in self.api_keys]  # Thoi diem key het han cooldown
        self.current_client_idx = 0
        
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []

    def _get_available_client(self) -> tuple[int, genai.Client]:
        """
        Lay client hop le khong bi vuong cooldown.
        Neu tat ca deu dang cooldown, ngu cho toi khi key gan nhat hoi phuc.
        """
        now = time.time()
        # Tim key san sang
        for _ in range(len(self.clients)):
            idx = self.current_client_idx
            self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
            if now >= self.key_cooldowns[idx]:
                return idx + 1, self.clients[idx]
                
        # Neu tat ca deu dang bi cooldown: ngu cho toi khi key som nhat san sang
        earliest_wait = min(self.key_cooldowns) - now
        if earliest_wait > 0:
            print(f"\n[RATE LIMIT] Tat ca {len(self.clients)} keys dang can nghi, tam dung {earliest_wait:.1f}s...")
            time.sleep(earliest_wait + 1.0)
            
        idx = self.current_client_idx
        self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
        return idx + 1, self.clients[idx]

    def embed_texts_with_rotation(self, texts: List[str], output_dir: Path, batch_size: int = 20, delay_seconds: float = 4.0) -> np.ndarray:
        """
        Nhung vector cho danh sach text voi co che xoay tua API Key va Checkpoint an toan.
        """
        checkpoint_file = output_dir / "embeddings_cache.npy"
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        # 1. Kiem tra va tai lai checkpoint cu neu co
        all_embeddings = []
        start_batch_idx = 0
        if checkpoint_file.exists():
            try:
                cached = np.load(str(checkpoint_file))
                if len(cached) == len(texts):
                    print(f"[CACHE] Phat hien toan bo {len(cached):,} vectors da duoc embed tu truoc! Su dung luon.")
                    vectors_np = np.array(cached, dtype=np.float32)
                    faiss.normalize_L2(vectors_np)
                    return vectors_np
                elif len(cached) > 0 and len(cached) < len(texts):
                    all_embeddings = list(cached)
                    start_batch_idx = len(all_embeddings) // batch_size
                    print(f"[CHECKPOINT] Tim thay {len(all_embeddings):,}/{len(texts):,} doan da embed. Tiep tuc tu batch {start_batch_idx + 1}/{total_batches}...")
            except Exception as e:
                print(f"[CHECKPOINT] Loi doc cache ({e}), bat dau moi.")
                all_embeddings = []
                start_batch_idx = 0

        # 2. Xu ly cac batch con lai
        b_idx = start_batch_idx
        while b_idx < total_batches:
            i = b_idx * batch_size
            batch = texts[i:i + batch_size]
            current_batch_num = b_idx + 1
            
            success = False
            attempts = 0
            max_attempts = len(self.clients) * 3
            
            while not success and attempts < max_attempts:
                client_id, client = self._get_available_client()
                attempts += 1
                
                print(f"[EMBEDDING] Batch {current_batch_num}/{total_batches} ({len(batch)} doan) [Key #{client_id}]...", end=" ", flush=True)
                
                try:
                    response = client.models.embed_content(
                        model=self.embedding_model,
                        contents=batch,
                        config=types.EmbedContentConfig(output_dimensionality=self.dimension)
                    )
                    batch_vectors = [emb.values for emb in response.embeddings]
                    all_embeddings.extend(batch_vectors)
                    success = True
                    print("[OK]")
                    
                    # Luu cache lien tuc sau moi 3 batch
                    if current_batch_num % 3 == 0 or current_batch_num == total_batches:
                        np.save(str(checkpoint_file), np.array(all_embeddings, dtype=np.float32))
                        
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        # Dat cooldown 65s rieng cho key bi 429, cac key khac van chay binh thuong
                        self.key_cooldowns[client_id - 1] = time.time() + 65.0
                        print(f"[429 Key #{client_id} nghi 65s -> Chuyen ngay sang Key khac]")
                    else:
                        print(f"[LOI: {e}] -> Thu key tiep theo")
                        time.sleep(2.0)
                        
            if not success:
                print(f"\n[CANH BAO] Khong the gui batch {current_batch_num}. Nghi 30 giay thu lai...")
                time.sleep(30.0)
                continue
                
            b_idx += 1
            if b_idx < total_batches:
                time.sleep(delay_seconds)
                
        vectors_np = np.array(all_embeddings, dtype=np.float32)
        # Luu tru cache vinh vien de khong bao gio bi mat
        np.save(str(checkpoint_file), vectors_np)
        
        # Chuan hoa L2 de phep nhan Inner Product thanh Cosine Similarity
        faiss.normalize_L2(vectors_np)
        return vectors_np

    def build_from_chunks_file(self, chunks_path: Path, output_dir: Path, batch_size: int = 20) -> None:
        """
        Doc file chunks.json, tao vector index va luu xuong thu muc output_dir bang Python File I/O.
        """
        print("=" * 70)
        print("KHOI TAO VECTOR DATABASE FAISS (MULTI-KEY ROTATION)")
        print(f"File nguon:    {chunks_path}")
        print(f"Thu muc luu:   {output_dir}")
        print(f"So luong Keys: {len(self.api_keys)}")
        print("=" * 70)
        
        if not chunks_path.exists():
            raise FileNotFoundError(f"Khong tim thay file chunks: {chunks_path}")
            
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
        total_chunks = len(chunks)
        print(f"[INFO] Tong so chunks can nhung vector: {total_chunks:,}")
        
        texts = [c["content"] for c in chunks]
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Tao vector embedding
        start_time = time.time()
        vectors = self.embed_texts_with_rotation(texts, output_dir=output_dir, batch_size=batch_size, delay_seconds=2.0)
        duration = time.time() - start_time
        print(f"\n[INFO] Hoan tat sinh {len(vectors):,} vectors trong {duration:.1f} giay.")
        
        # 2. Xay dung FAISS Index Flat Inner Product
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(vectors)
        self.metadata = chunks
        
        # 3. Luu xuong dia bang serialize_index (Tranh loi duong dan tieng Viet tren Windows)
        index_file = output_dir / "faiss_index.bin"
        metadata_file = output_dir / "chunks_metadata.json"
        
        serialized_bytes = faiss.serialize_index(self.index).tobytes()
        with open(index_file, "wb") as f:
            f.write(serialized_bytes)
            
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
        print("\n" + "=" * 70)
        print("DA LUU THANH CONG VECTOR DATABASE:")
        print(f"1. Index FAISS:     {index_file} ({os.path.getsize(index_file) / (1024 * 1024):.2f} MB)")
        print(f"2. Metadata JSON:   {metadata_file} ({os.path.getsize(metadata_file) / (1024 * 1024):.2f} MB)")
        print(f"3. Tong so records: {self.index.ntotal:,}")
        print("=" * 70)

    def load(self, vectorstore_dir: Path) -> None:
        """
        Load FAISS Index va Metadata tu dia vao bo nho RAM (ho tro Unicode path tren Windows).
        """
        index_file = vectorstore_dir / "faiss_index.bin"
        metadata_file = vectorstore_dir / "chunks_metadata.json"
        
        if not index_file.exists() or not metadata_file.exists():
            raise FileNotFoundError(f"Khong tim thay du lieu Vector Store tai: {vectorstore_dir}")
            
        with open(index_file, "rb") as f:
            raw_bytes = np.frombuffer(f.read(), dtype=np.uint8)
        self.index = faiss.deserialize_index(raw_bytes)
        
        with open(metadata_file, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
            
        print(f"[VECTORSTORE] Da load thanh cong {self.index.ntotal:,} vectors tu {vectorstore_dir.name}.")

    def search(self, query: str, top_k: int = 4, threshold: float = 0.55) -> Dict[str, Any]:
        """
        Tim kiem Top-K doan trich tuong dong nhat voi cau hoi cua nguoi dung.
        - Tinh Cosine Similarity.
        - Loc theo nguong tin cay (threshold).
        - Tra ve ket qua phan loai: co can cu hay khong (is_grounded).
        """
        if self.index is None or not self.metadata:
            raise RuntimeError("Vector Store chua duoc khoi tao hoac load vao bo nho!")
            
        # Lay 1 client de embed cau hoi query
        _, client = self._get_available_client()
        response = client.models.embed_content(
            model=self.embedding_model,
            contents=[query],
            config=types.EmbedContentConfig(output_dimensionality=self.dimension)
        )
        query_vector = np.array([response.embeddings[0].values], dtype=np.float32)
        faiss.normalize_L2(query_vector)
        
        # Truy van FAISS
        scores, indices = self.index.search(query_vector, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
                
            item = dict(self.metadata[idx])
            item["similarity_score"] = float(score)
            
            # Chi lay nhung doan vuot nguong tin cay
            if score >= threshold:
                results.append(item)
                
        is_grounded = len(results) > 0
        
        return {
            "query": query,
            "top_k_found": len(results),
            "is_grounded": is_grounded,
            "threshold": threshold,
            "chunks": results
        }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    chunks_json_path = base_dir / "data" / "processed" / "chunks.json"
    vector_dir = base_dir / "data" / "vectorstore"
    
    store = UteeVectorStore()
    
    index_bin = vector_dir / "faiss_index.bin"
    if not index_bin.exists():
        print("[INFO] Chua co Vector Store hoan chinh. Tien hanh build tu chunks.json...")
        store.build_from_chunks_file(chunks_json_path, vector_dir, batch_size=20)
    else:
        print("[INFO] Vector Store da ton tai. Tien hanh load de kiem thu...")
        store.load(vector_dir)
        
    # Kiem thu tim kiem cau hoi thuc te
    test_queries = [
        "Sinh vien bi diem F hoc phan thi phai lam gi?",
        "Dieu kien de duoc xet hoc bong khuyen khich hoc tap la gi?",
        "Hoc phi nam hoc 2026-2027 cua truong nhu the nao?"
    ]
    
    print("\n" + "=" * 70)
    print("KIEM THU TRUY VAN COSINE SIMILARITY TREN VECTOR DATABASE")
    print("=" * 70)
    for q in test_queries:
        res = store.search(q, top_k=2, threshold=0.55)
        print(f"\n[CAU HOI]: \"{q}\"")
        print(f"Trang thai tin cay: {'CO CAN CU' if res['is_grounded'] else 'KHONG DU CAN CU'}")
        for c in res["chunks"]:
            print(f"  -> [{c['similarity_score']:.4f}] {c['doc_title']} ({c['section']}, Trang {c['page']})")
