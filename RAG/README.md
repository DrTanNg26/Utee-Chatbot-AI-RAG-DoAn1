# MODULE AI & RAG PIPELINE - CHATBOT UTEE
> Học phần: Đồ án 1 - Hệ thống Chatbot AI UTee (Sinh viên UTT)  
> Chuyên trách: Dữ liệu & AI RAG Pipeline

---

## 1. Giới thiệu tổng quan
Module RAG (Retrieval-Augmented Generation) là trung tâm tri thức của Chatbot UTee, chịu trách nhiệm:
1. Tra cứu chính xác các quy chế, biểu mẫu, học bổng, điểm rèn luyện và đề cương học phần UTT dựa trên tài liệu có nguồn dẫn xác thực.
2. Kiểm soát ngưỡng tin cậy (Confidence Threshold >= 0.60) để kích hoạt cơ chế **Từ chối an toàn (Safe Refusal)**, triệt tiêu hoàn toàn hiện tượng AI bịa đặt (hallucination).
3. Đính kèm trích dẫn nguồn chi tiết (Tên tài liệu, Điều/Khoản, Số trang) cho mỗi câu trả lời.

---

## 2. Hướng dẫn chạy nhanh cho Thành viên nhóm (Quick Start)

Dữ liệu Vector Database (`faiss_index.bin`) **đã được biên dịch sẵn đầy đủ 2,174 chunks trong repo**. Các bạn trong nhóm **KHÔNG CẦN** phải chạy lại quá trình băm đoạn hay embedding tốn thời gian.

Chỉ cần làm đúng 3 bước sau:

### Bước 1: Cài đặt thư viện
Mở Terminal tại thư mục gốc của dự án và chạy:
```bash
pip install -r RAG/requirements.txt
```

### Bước 2: Thiết lập API Key
1. Tạo 1 file tên `.env` tại thư mục gốc dự án (nằm cạnh file `.env.example`).
2. Lấy API Key miễn phí tại [Google AI Studio](https://aistudio.google.com/).
3. Dán key vào file `.env`:
```env
GEMINI_API_KEY=AIzaSy...
```

### Bước 3: Chạy thử nghiệm Chatbot ngay trên Terminal
Chạy lệnh sau:
```bash
python -c "import sys; sys.path.insert(0, 'RAG/src'); from rag_engine import run_interactive_cli; run_interactive_cli()"
```
Gõ bất kỳ câu hỏi nào về quy chế UTT (ví dụ: *"Học bổng loại Giỏi cần điều kiện gì?"*, *"Môn Toán 1 có bao nhiêu tín chỉ?"*) để trải nghiệm.

---

## 3. Hướng dẫn tích hợp vào Backend FastAPI (Dành cho thành viên Backend)

Thành viên phụ trách Backend chỉ cần gọi class `UteeRagEngine` trong API endpoint chat như sau:

```python
import sys
from pathlib import Path

# Thêm thư mục RAG/src vào sys.path nếu cần
sys.path.insert(0, str(Path(__file__).resolve().parent / "RAG" / "src"))

from rag_engine import UteeRagEngine

# Khởi tạo engine 1 lần duy nhất khi khởi động Backend
rag_engine = UteeRagEngine()

# Trong hàm xử lý API route:
def handle_chat_message(user_query: str):
    response = rag_engine.answer_question(user_query)
    
    answer_text = response["answer"]              # Câu trả lời tiếng Việt chuẩn của UTee
    is_grounded = response["is_grounded"]          # True: Có căn cứ quy chế | False: Ngoài lề (Safe Refusal)
    confidence = response["confidence_score"]      # Điểm tương đồng Cosine (0.0 -> 1.0)
    citations = response["citations"]              # Danh sách nguồn trích dẫn: file, Điều, trang
    
    return {
        "reply": answer_text,
        "is_grounded": is_grounded,
        "confidence": confidence,
        "citations": citations
    }
```

---

## 4. Cấu trúc thư mục Module RAG

```text
RAG/
├── data/
│   ├── raw/                 # 68 tài liệu gốc UTT (.pdf, .docx, .xlsx)
│   │   ├── de-cuong-k73-cntt/ # 40 đề cương môn học chuyên ngành CNTT
│   │   └── ...              # Quy chế đào tạo, học bổng, rèn luyện, KTX, thư viện...
│   ├── processed/
│   │   └── chunks.json      # 2,174 đoạn văn bản đã băm theo Điều/Khoản kèm Metadata
│   └── vectorstore/
│       ├── faiss_index.bin  # CSDL Vector FAISS chuẩn hóa L2 (6.67 MB)
│       ├── chunks_metadata.json # Metadata liên kết cho từng vector
│       └── embeddings_cache.npy # Cache vector vĩnh viễn (chạy lại chỉ mất 0.05s)
├── src/
│   ├── parser.py            # Trích xuất và làm sạch văn bản (PDF, DOCX, XLSX), chuẩn hóa Unicode NFC
│   ├── chunker.py           # Băm nhỏ thông minh theo Điều / Khoản quy chế UTT
│   ├── build_dataset.py     # Script điều phối tạo file chunks.json từ data/raw/
│   ├── vectorstore.py       # Quản lý FAISS, Google Gemini Embedding và Key Rotation
│   └── rag_engine.py        # Bộ não RAG: Safe Refusal Gate, Grounding System Prompt, CLI Chat
├── requirements.txt         # Thư viện cần thiết cho module RAG
└── README.md                # Tài liệu kỹ thuật này
```

---

## 5. Thống kê kỹ thuật phục vụ Báo cáo & Bảo vệ Đồ án
* **Quy mô dữ liệu nguồn:** 68 văn bản, thông tư, quyết định chính thức của UTT.
* **Tổng số Chunks:** 2,174 đoạn có cấu trúc.
* **Độ dài trung bình:** 832 ký tự / chunk (~208 tokens), kiểm soát tối đa < 1,312 ký tự.
* **Mô hình Embedding:** Google Gemini `gemini-embedding-001` (Output dimension: 768).
* **Độ tương đồng:** FAISS `IndexFlatIP` kết hợp L2 Normalization (tính toán chuẩn xác Cosine Similarity).
* **Cơ chế phòng vệ:** Ngưỡng tin cậy (Confidence Threshold = 0.60). Mọi truy vấn không có căn cứ đều được kích hoạt Safe Refusal trước khi gọi LLM.
* **Mô hình ngôn ngữ (LLM):** `gemini-3.5-flash` với nhiệt độ thấp (temperature = 0.2) chống ảo giác.
