"""
chunker.py - Module phân đoạn văn bản thông minh (Semantic Chunking) cho quy chế UTT.
Học phần: Đồ án 1 - Hệ thống Chatbot AI UTee
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Đảm bảo in tiếng Việt an toàn trên terminal Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Bảng ánh xạ phân loại tài liệu tự động dựa trên tên file
DOCUMENT_METADATA_MAP = {
    "01-quy-che-clb": ("CLB & Đội nhóm", "Quy chế câu lạc bộ, đội nhóm sinh viên 2016"),
    "02-quy-dinh-hoc-bong": ("Học bổng & Học phí", "Quy định học bổng khuyến khích học tập 2024"),
    "03-quy-dinh-thi-sinh-vien-gioi": ("Khen thưởng & Cuộc thi", "Quy định thi sinh viên giỏi, Olympic 2024"),
    "04-quy-che-van-phong-tiep-cong-dan": ("Hành chính & Thủ tục", "Quy chế văn phòng tiếp công dân và người học 2024"),
    "05-quy-che-danh-gia-ren-luyen": ("Điểm rèn luyện", "Quy chế đánh giá kết quả rèn luyện sinh viên 2023"),
    "06-quy-dinh-ban-can-su": ("Tổ chức lớp học", "Quy định ban cán sự lớp sinh viên 2024"),
    "07-quy-dinh-chu-nhiem-lop": ("Cố vấn học tập", "Quy định chủ nhiệm lớp và cố vấn học tập 2023"),
    "08-quy-dinh-mien-giam-hoc-phi": ("Học bổng & Học phí", "Quy định miễn giảm học phí và trợ cấp xã hội 2024"),
    "09-quy-dinh-van-hoa-hoc-duong": ("Nội quy & Đời sống", "Quy định văn hóa học đường 2021"),
    "10-noi-quy-hoc-duong": ("Nội quy & Đời sống", "Nội quy học đường đối với sinh viên 2024"),
    "20-quy-che-dao-tao-dai-hoc": ("Quy chế đào tạo", "Quy chế đào tạo đại học chính quy 2024 (QĐ 1710)"),
    "22-qd-6500-chuan-dau-ra-ngoai-ngu": ("Chuẩn đầu ra", "Quy định chuẩn đầu ra ngoại ngữ (QĐ 6500)"),
    "23-quy-dinh-chuan-dau-ra-cong-nghe-thong-tin": ("Chuẩn đầu ra", "Quy định chuẩn đầu ra ngành Công nghệ thông tin 2022"),
    "cam_nang_huong_dan_diem_ren_luyen": ("Điểm rèn luyện", "Cẩm nang hướng dẫn đánh giá điểm rèn luyện UTT"),
    "ctdt-k73-cong-nghe-thong-tin": ("Chương trình đào tạo", "Chương trình đào tạo K73 ngành Công nghệ thông tin"),
    "huong-dan-dang-ky-hoc": ("Đăng ký tín chỉ", "Hướng dẫn đăng ký học trên cổng đào tạo UTT"),
    "huong-dan-dang-ky-noi-tru": ("Ký túc xá", "Hướng dẫn đăng ký nội trú Ký túc xá"),
    "huong-dan-hanh-chinh-dien-tu": ("Hành chính & Thủ tục", "Hướng dẫn thủ tục hành chính điện tử sinh viên 2025"),
    "ke-hoach-dao-tao": ("Kế hoạch đào tạo", "Kế hoạch thời gian đào tạo đại học chính quy"),
    "mo-ta-ctdt": ("Chương trình đào tạo", "Mô tả chi tiết chương trình đào tạo K73 CNTT"),
    "noi-quy": ("Thư viện", "Nội quy phòng đọc và mượn sách thư viện UTT"),
    "quy-trinh-muon-sach": ("Thư viện", "Quy trình mượn sách mang về thư viện"),
    "thong-bao-khai-thac-thu-vien": ("Thư viện", "Thông báo khai thác thư viện số UTT"),
    "thong-bao-muc-thu-hoc-phi": ("Học bổng & Học phí", "Thông báo mức thu học phí năm học 2026-2027"),
}


def get_doc_metadata(file_name: str) -> tuple[str, str]:
    """
    Tự động suy ra (Chuyên mục, Tên tài liệu chuẩn) từ tên file.
    """
    clean_name = file_name.lower()
    
    # Nhận diện đề cương học phần
    if clean_name.startswith("dc") or "de-cuong" in clean_name:
        return ("Đề cương môn học", f"Đề cương chi tiết học phần: {file_name}")
        
    for key, (category, title) in DOCUMENT_METADATA_MAP.items():
        if key in clean_name:
            return (category, title)
            
    return ("Tài liệu UTT", file_name)


def split_text_into_articles(full_text: str) -> List[Dict[str, str]]:
    """
    Băm văn bản theo cấu trúc Điều / Mục của quy chế.
    Ví dụ: 'Điều 1.', 'Điều 14: Đăng ký học lại...', 'CHƯƠNG II...'
    """
    # Regex tìm các tiêu đề Điều khoản hoặc Chương
    pattern = r"(?=(?:^|\n)(?:CHƯƠNG\s+[IVXLCDM\d]+[^\n]*|Điều\s+\d+[\.:\s][^\n]*|[IVXLCDM]+\.\s+[A-ZÀ-ỸĐ][^\n]*))"
    
    parts = re.split(pattern, full_text, flags=re.MULTILINE)
    sections = []
    current_chapter = ""
    
    for part in parts:
        part_clean = part.strip()
        if not part_clean:
            continue
            
        first_line = part_clean.split("\n")[0].strip()
        
        # Nếu là dòng CHƯƠNG, ghi nhớ lại để làm ngữ cảnh cho các Điều tiếp theo
        if re.match(r"^CHƯƠNG\s+[IVXLCDM\d]+", first_line, re.IGNORECASE):
            current_chapter = first_line
            # Vẫn lưu nội dung chương nếu có phần mở đầu
            sections.append({
                "section_title": first_line,
                "content": part_clean
            })
            continue
            
        # Nếu là Điều
        if re.match(r"^Điều\s+\d+", first_line, re.IGNORECASE):
            section_title = first_line
            if current_chapter:
                section_title = f"{current_chapter} - {section_title}"
            sections.append({
                "section_title": section_title,
                "content": part_clean
            })
            continue
            
        # Các mục La Mã hoặc phần mở đầu (Quyết định, Căn cứ pháp lý)
        sections.append({
            "section_title": first_line[:100],
            "content": part_clean
        })
        
    return sections


def recursive_sub_chunk(text: str, max_chars: int = 1200, overlap_chars: int = 150) -> List[str]:
    """
    Chia nho van ban vuot qua max_chars theo thu tu uu tien:
    1. Doan van (\\n\\n)
    2. Dong van ban / dong bang bieu (\\n)
    3. Cau van ket thuc bang [.!?]
    4. Cat cuong neu 1 dong duy nhat vuot qua max_chars.
    """
    if len(text) <= max_chars:
        return [text]

    # Buoc 1: Thu tach theo doan van (\\n\\n)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Neu chi co 1 doan duy nhat (nhu bang bieu noi bang \\n), tach theo dong (\\n)
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in text.split("\n") if line.strip()]

    # Buoc 2: Xu ly tung phan tu, neu phan tu nao > max_chars thi tach tiep
    atomic_pieces = []
    for p in paragraphs:
        if len(p) <= max_chars:
            atomic_pieces.append(p)
        else:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]
            if len(sentences) > 1:
                for s in sentences:
                    if len(s) <= max_chars:
                        atomic_pieces.append(s)
                    else:
                        for i in range(0, len(s), max_chars - overlap_chars):
                            sub_s = s[i:i + max_chars].strip()
                            if sub_s:
                                atomic_pieces.append(sub_s)
            else:
                for i in range(0, len(p), max_chars - overlap_chars):
                    sub_p = p[i:i + max_chars].strip()
                    if sub_p:
                        atomic_pieces.append(sub_p)

    # Buoc 3: Dong goi vao cac chunk voi nguong max_chars va overlap
    chunks = []
    current_chunk = ""

    for piece in atomic_pieces:
        separator = "\n"
        tentative_length = len(current_chunk) + len(separator) + len(piece) if current_chunk else len(piece)

        if tentative_length <= max_chars:
            current_chunk = f"{current_chunk}{separator}{piece}".strip() if current_chunk else piece
        else:
            if current_chunk:
                chunks.append(current_chunk)
                overlap_text = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else ""
                current_chunk = f"{overlap_text}{separator}{piece}".strip() if overlap_text else piece
            else:
                chunks.append(piece)
                current_chunk = ""

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_document_items(doc_items: List[Dict[str, Any]], max_chars: int = 1000, overlap_chars: int = 150) -> List[Dict[str, Any]]:
    """
    Hàm phân đoạn tổng thể từ danh sách các trang/phần do parser.py trả về.
    Mỗi chunk sinh ra đều mang đầy đủ Metadata để phục vụ truy xuất RAG và Citation.
    """
    final_chunks = []
    if not doc_items:
        return final_chunks
        
    source_file = doc_items[0]["source"]
    category, doc_title = get_doc_metadata(source_file)
    
    # Gom toàn bộ nội dung của file (kèm theo số trang xuất hiện)
    full_text = ""
    page_map = {}  # Lưu vị trí ký tự tương ứng với số trang
    
    current_char_offset = 0
    for item in doc_items:
        page_num = item.get("page", 1)
        text_content = item.get("text", "")
        page_map[current_char_offset] = page_num
        full_text += text_content + "\n\n"
        current_char_offset = len(full_text)
        
    # 1. Băm theo cấu trúc Điều/Khoản
    raw_sections = split_text_into_articles(full_text)
    
    chunk_index = 1
    running_offset = 0
    
    for sec in raw_sections:
        sec_title = sec["section_title"]
        sec_content = sec["content"]
        
        # Xác định trang xuất hiện của đoạn này
        matched_page = 1
        for offset, p_num in page_map.items():
            if running_offset >= offset:
                matched_page = p_num
            else:
                break
                
        running_offset += len(sec_content)
        
        # 2. Kiểm tra độ dài: Nếu Điều quá dài -> Cắt nhỏ (sub-chunk)
        sub_chunks = recursive_sub_chunk(sec_content, max_chars=max_chars, overlap_chars=overlap_chars)
        
        for idx, sub_text in enumerate(sub_chunks):
            # Nếu là sub-chunk, ghi chú rõ phần
            display_title = sec_title
            if len(sub_chunks) > 1:
                display_title = f"{sec_title} (Phần {idx + 1}/{len(sub_chunks)})"
                
            # Đính kèm ngữ cảnh nguồn vào nội dung chunk để embedding hiểu trọn vẹn
            context_header = f"[{doc_title}] - {display_title}\n"
            enriched_content = f"{context_header}{sub_text}"
            
            chunk_data = {
                "chunk_id": f"{Path(source_file).stem}_c{chunk_index:03d}",
                "source": source_file,
                "doc_title": doc_title,
                "category": category,
                "section": display_title,
                "page": matched_page,
                "content": enriched_content,
                "char_count": len(enriched_content),
                "token_estimate": len(enriched_content) // 4  # Ước tính 1 token ~ 4 ký tự tiếng Việt
            }
            final_chunks.append(chunk_data)
            chunk_index += 1
            
    return final_chunks


if __name__ == "__main__":
    from parser import parse_document
    
    print("=" * 65)
    print("KIEM THU BAM NHO NGU NGHIA (CHUNKER) TREN QUY CHE DAO TAO UTT")
    print("=" * 65)
    
    sample_file = Path(__file__).resolve().parent.parent / "data" / "raw" / "20-quy-che-dao-tao-dai-hoc-2024-qd-1710.pdf"
    
    if not sample_file.exists():
        print(f"Khong tim thay file: {sample_file}")
    else:
        print(f"\n1. Dang trich xuat trang tu: {sample_file.name}...")
        parsed_items = parse_document(sample_file)
        print(f"   -> Doc duoc {len(parsed_items)} trang.")
        
        print("\n2. Dang thuc hien Semantic Chunking (Dieu / Khoan / Ngu canh)...")
        chunks = chunk_document_items(parsed_items, max_chars=1000, overlap_chars=150)
        print(f"   -> Da bam thanh cong: {len(chunks)} Chunks co cau truc.")
        
        print("\n3. Mau 2 Chunks tieu bieu vua tao:")
        for sample in chunks[10:12]:
            print("-" * 50)
            print(f"ID: {sample['chunk_id']}")
            print(f"Tai lieu: {sample['doc_title']}")
            print(f"Chuyen muc: {sample['category']}")
            print(f"Tieu de Dieu: {sample['section']}")
            print(f"So trang: {sample['page']}")
            print(f"Do dai: {sample['char_count']} ky tu (~{sample['token_estimate']} tokens)")
            print("Noi dung doan trich:")
            lines = sample['content'].split("\n")
            preview = "\n".join(lines[:6]) + "\n..." if len(lines) > 6 else sample['content']
            print(preview)
            
        print("\n" + "=" * 65)
        print("THU NGHIEM BAM DOAN HOAN TAT THANH CONG!")
        print("=" * 65)
