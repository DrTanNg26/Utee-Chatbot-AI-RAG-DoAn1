"""
build_dataset.py - Module dieu phoi toan bo quy trinh doc, lam sach, bam doan (RAG Ingestion Pipeline)
va xuat du lieu ra file chunks.json.
Hoc phan: Do an 1 - He thong Chatbot AI UTee
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any

# Dam bao in tieng Viet an toan tren terminal Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Import module noi bo
from parser import parse_document
from chunker import chunk_document_items


def is_valid_file(file_path: Path) -> bool:
    """
    Kiem tra file co hop le de xu ly hay khong:
    - Bo qua file an hoac file tam thoi cua Microsoft Office (co tien to ~$).
    - Chi nhan cac dinh dang .docx, .pdf, .xlsx.
    """
    if file_path.name.startswith("~$") or file_path.name.startswith("."):
        return False
    return file_path.suffix.lower() in [".docx", ".pdf", ".xlsx", ".xls"]


def build_rag_dataset(raw_dir: Path, output_file: Path) -> List[Dict[str, Any]]:
    """
    Duyet toan bo file trong thu muc data/raw, goi parser va chunker,
    sau do gom thanh file JSON hoan chinh.
    """
    start_time = time.time()
    
    print("=" * 70)
    print("BAT DAU XAY DUNG KHO DU LIEU RAG (BUILD DATASET) - UTEE CHATBOT")
    print(f"Thu muc nguon: {raw_dir}")
    print(f"File dau ra:   {output_file}")
    print("=" * 70)
    
    if not raw_dir.exists():
        print(f"[LOI] Thu muc nguon khong ton tai: {raw_dir}")
        return []
        
    # Lay toan bo file can xu ly
    all_files = [f for f in raw_dir.rglob("*") if f.is_file() and is_valid_file(f)]
    total_files = len(all_files)
    print(f"[INFO] Tim thay tong cong {total_files} file hop le can xu ly.\n")
    
    all_chunks = []
    success_count = 0
    failed_files = []
    
    # Global chunk index de tao ID duy nhat cho toan bo he thong
    global_chunk_idx = 1
    
    for idx, file_path in enumerate(all_files, start=1):
        relative_path = file_path.relative_to(raw_dir)
        print(f"[{idx:02d}/{total_files:02d}] Dang xu ly: {relative_path}...", end=" ", flush=True)
        
        try:
            # 1. Trich xuat noi dung chu tu file
            doc_items = parse_document(file_path)
            if not doc_items:
                print("[BO QUA] (Khong co noi dung chu)")
                continue
                
            # 2. Bam nho theo ngu nghia Dieu / Khoan
            file_chunks = chunk_document_items(doc_items, max_chars=1000, overlap_chars=150)
            
            # Gan global ID cho tung chunk
            for c in file_chunks:
                c["global_id"] = global_chunk_idx
                global_chunk_idx += 1
                
            all_chunks.extend(file_chunks)
            success_count += 1
            print(f"[OK] -> {len(file_chunks)} chunks.")
            
        except Exception as e:
            print(f"[THAT BAI] ({e})")
            failed_files.append((str(relative_path), str(e)))
            
    # 3. Luu ket qua vao file JSON
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
    duration = time.time() - start_time
    
    # 4. Thong ke ket qua
    print("\n" + "=" * 70)
    print("KET QUA XU LY KHO DU LIEU RAG HOAN TAT")
    print(f"- Thoi gian thuc hien:     {duration:.2f} giay")
    print(f"- So file xu ly thanh cong: {success_count}/{total_files}")
    if failed_files:
        print(f"- So file loi:              {len(failed_files)}")
        for fn, err in failed_files:
            print(f"  + {fn}: {err}")
    print(f"- Tong so Chunks tao ra:   {len(all_chunks):,} chunks")
    
    if all_chunks:
        # Thong ke theo Chuyen muc
        category_counts = Counter(c["category"] for c in all_chunks)
        print("\n--- Phan bo Chunks theo Chuyen muc ---")
        for cat, cnt in category_counts.most_common():
            percentage = (cnt / len(all_chunks)) * 100
            print(f"  * {cat:<30}: {cnt:>4} chunks ({percentage:>5.1f}%)")
            
        # Thong ke ve do dai
        char_counts = [c["char_count"] for c in all_chunks]
        token_estimates = [c["token_estimate"] for c in all_chunks]
        avg_chars = sum(char_counts) / len(char_counts)
        avg_tokens = sum(token_estimates) / len(token_estimates)
        print("\n--- Thong so do dai Chunk ---")
        print(f"  * Do dai ky tu trung binh: {avg_chars:.0f} ky tu (Nho nhat: {min(char_counts)}, Lon nhat: {max(char_counts)})")
        print(f"  * So token uoc tinh trung binh: {avg_tokens:.0f} tokens (Chuan toi uu cho LLM)")
        
    print(f"\n[DA LUU]: {output_file}")
    print("=" * 70)
    
    return all_chunks


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    raw_directory = base_dir / "data" / "raw"
    processed_file = base_dir / "data" / "processed" / "chunks.json"
    
    build_rag_dataset(raw_directory, processed_file)
