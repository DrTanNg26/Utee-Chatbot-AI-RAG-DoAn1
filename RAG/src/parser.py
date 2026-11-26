"""
parser.py - Module trích xuất và làm sạch văn bản từ các định dạng tài liệu UTT (.docx, .pdf, .xlsx).
Học phần: Đồ án 1 - Hệ thống Chatbot AI UTee
"""

import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any

# Đảm bảo in tiếng Việt và ký tự đặc biệt an toàn trên terminal Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import docx
from pypdf import PdfReader
import openpyxl


def clean_text(text: str) -> str:
    """
    Chuẩn hóa văn bản tiếng Việt:
    - Chuẩn hóa Unicode dạng NFC (tránh lỗi ký tự tổ hợp tiếng Việt).
    - Loại bỏ các ký tự vô hình, khoảng trắng thừa và dòng trống lặp lại.
    """
    if not text:
        return ""
    
    # 1. Chuẩn hóa Unicode NFC
    text = unicodedata.normalize("NFC", text)
    
    # 2. Xóa ký tự điều khiển lạ nhưng giữ lại xuống dòng (\n) và tab (\t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    
    # 3. Chuẩn hóa khoảng trắng ngang (tab, non-breaking space -> dấu cách thường)
    text = re.sub(r"[ \t\u00a0\u200b]+", " ", text)
    
    # 4. Rút gọn nhiều dòng trống liên tiếp (chỉ giữ tối đa 2 dòng ngắt)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    
    return text.strip()


def parse_docx(file_path: Path) -> List[Dict[str, Any]]:
    """
    Trích xuất văn bản từ file Word (.docx), bao gồm cả đoạn văn và bảng biểu.
    """
    doc = docx.Document(str(file_path))
    extracted = []
    
    # 1. Đọc từng đoạn văn bản (paragraphs)
    full_paragraphs = []
    for p in doc.paragraphs:
        txt = clean_text(p.text)
        if txt:
            full_paragraphs.append(txt)
            
    # 2. Đọc các bảng biểu (tables) và chuyển đổi sang dạng bảng Markdown
    table_texts = []
    for table in doc.tables:
        rows_data = []
        for row in table.rows:
            # Lấy text từng cell, loại bỏ trùng lặp nếu cell bị merge
            cells = [clean_text(cell.text) for cell in row.cells]
            # Loại bỏ các cột trùng lặp do merge cell
            dedup_cells = []
            for c in cells:
                if not dedup_cells or c != dedup_cells[-1]:
                    dedup_cells.append(c)
            if any(dedup_cells):
                rows_data.append(" | ".join(dedup_cells))
        if rows_data:
            table_md = "\n".join(rows_data)
            table_texts.append(f"[BẢNG BIỂU]:\n{table_md}")
            
    # Gom nội dung văn bản và bảng biểu
    all_content = []
    if full_paragraphs:
        all_content.append("\n\n".join(full_paragraphs))
    if table_texts:
        all_content.append("\n\n".join(table_texts))
        
    combined_text = "\n\n".join(all_content)
    
    if combined_text:
        extracted.append({
            "source": file_path.name,
            "type": "docx",
            "page": 1,  # File docx thông thường xem như 1 luồng văn bản liền mạch
            "text": clean_text(combined_text)
        })
        
    return extracted


def parse_pdf(file_path: Path) -> List[Dict[str, Any]]:
    """
    Trích xuất văn bản từ file PDF theo từng trang.
    Ghi nhớ chính xác số trang (page_number) để phục vụ trích dẫn nguồn (Citations).
    """
    reader = PdfReader(str(file_path))
    extracted = []
    
    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)
        
        # Chỉ lấy những trang có nội dung chữ thực sự (bỏ qua trang trống)
        if len(cleaned) >= 20:
            extracted.append({
                "source": file_path.name,
                "type": "pdf",
                "page": page_num,
                "text": cleaned
            })
            
    return extracted


def parse_excel(file_path: Path) -> List[Dict[str, Any]]:
    """
    Trích xuất dữ liệu từ bảng tính Excel (.xlsx), định dạng thành bảng đọc dễ hiểu.
    """
    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    extracted = []
    
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        rows = list(sheet.iter_rows(values_only=True))
        
        sheet_lines = [f"[SHEET: {sheet_name}]"]
        for row in rows:
            # Lọc các ô không rỗng
            valid_cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if valid_cells:
                sheet_lines.append(" | ".join(valid_cells))
                
        if len(sheet_lines) > 1:
            sheet_content = "\n".join(sheet_lines)
            extracted.append({
                "source": file_path.name,
                "type": "xlsx",
                "page": sheet_name,
                "text": clean_text(sheet_content)
            })
            
    return extracted


def parse_document(file_path: Path) -> List[Dict[str, Any]]:
    """
    Hàm điều phối tổng: Tự động nhận diện đuôi file để gọi parser tương ứng.
    """
    ext = file_path.suffix.lower()
    if ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    elif ext in [".xlsx", ".xls"]:
        return parse_excel(file_path)
    else:
        print(f"Bỏ qua định dạng chưa hỗ trợ: {file_path.name}")
        return []


if __name__ == "__main__":
    # Chạy thử nghiệm trực tiếp trên 1 file Word và 1 file PDF của UTT
    sample_raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    
    print("=" * 60)
    print("KIỂM THỬ TRÍCH XUẤT VĂN BẢN (PARSER) TRÊN DỮ LIỆU UTT")
    print("=" * 60)
    
    # 1. Thử nghiệm file Word quy chế rèn luyện
    sample_docx = sample_raw_dir / "05-quy-che-danh-gia-ren-luyen-sinh-vien-2023.docx"
    if sample_docx.exists():
        print(f"\n Đang đọc file Word: {sample_docx.name}...")
        results_docx = parse_docx(sample_docx)
        for item in results_docx:
            print(f"   -> Đọc thành công! Độ dài văn bản: {len(item['text']):,} ký tự.")
            print("   -> 200 ký tự đầu tiên trích xuất được:")
            print("      " + repr(item['text'][:200]))
            
    # 2. Thử nghiệm file PDF quy chế đào tạo đại học
    sample_pdf = sample_raw_dir / "20-quy-che-dao-tao-dai-hoc-2024-qd-1710.pdf"
    if sample_pdf.exists():
        print(f"\n Đang đọc file PDF: {sample_pdf.name}...")
        results_pdf = parse_pdf(sample_pdf)
        print(f"   -> Đọc thành công {len(results_pdf)} trang có nội dung chữ.")
        if results_pdf:
            sample_page = results_pdf[0]
            print(f"   -> Trang {sample_page['page']}: {len(sample_page['text']):,} ký tự.")
            print("   -> 200 ký tự đầu trang:")
            print("      " + repr(sample_page['text'][:200]))
            
    print("\n" + "=" * 60)
    print("KIỂM THỬ HOÀN TẤT THÀNH CÔNG!")
    print("=" * 60)
