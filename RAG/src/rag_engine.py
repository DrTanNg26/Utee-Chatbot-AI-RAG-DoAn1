"""
rag_engine.py - Module dieu phoi hoi dap RAG (Retrieval-Augmented Generation) cho Chatbot UTee.
Ket hop giua tim kiem Vector FAISS va mo hinh ngon ngu Gemini kem Co che Tu choi an toan (Safe Refusal).
Hoc phan: Do an 1 - He thong Chatbot AI UTee
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Dam bao in tieng Viet an toan tren terminal Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Import module quan ly Vector Database
from vectorstore import UteeVectorStore


SYSTEM_PROMPT_TEMPLATE = """BAN LA UTEE - TRO LY AI DONG HANH VOI SINH VIEN TRUONG DAI HOC CONG NGHE GIAO THONG VAN TAI (UTT).

NHIEM VU:
Tra loi cau hoi cua sinh vien DUA HOAN TOAN vao cac doan trich thong tin [NGU CANH / CONTEXT] duoc cung cap duoi day.

CAC NGUYEN TAC BAT BUOC:
1. Tinh xac thuc: Tuyet doi khong tu suy dien, khong bia dat quy che hoac so lieu neu thong tin khong xuat hien trong [NGU CANH].
2. Trich dan nguon: Moi thong tin quy dinh phai dan chung ro rang trich tu tai lieu nao, Dieu/Khoan nao va Trang may (vi du: Theo Dieu 9, Quy che dao tao 2024, Trang 13...).
3. Xu ly khi thieu thong tin: Neu trong [NGU CANH] chi giai dap duoc mot phan cau hoi, hay tra loi day du phan da co can cu, sau do chu dong khuyen nghi sinh vien lien he Phong Dao tao hoac Co van hoc tap de duoc huong dan chi tiet them. Khong tu y bo do cau tra loi.
4. Giong van & Thai do: Than thien, le do, ho tro nhiet tinh, tieng Viet chuan muc, xung ho "UTee - ban" hoac "minh - ban".
"""


def detect_quick_intent(query: str) -> Optional[str]:
    """
    Nhan dien cac cau hoi giao tiep co ban (Loi chao, Dinh danh Bot, Cam on, Nang luc)
    de phan hoi ngay lap tuc ma khong can truy van FAISS hay kich hoat Safe Refusal.
    """
    q = query.lower().strip()
    
    # 1. Hoi ve danh tinh cua Bot
    if re.search(r"\b(bạn là ai|bạn tên gì|ai đấy|mày là ai|giới thiệu về bạn|bạn là gì|bot là ai|utee là ai)\b", q):
        return (
            "Chào bạn! Mình là UTee - Trợ lý AI đồng hành cùng sinh viên Trường Đại học Công nghệ Giao thông Vận tải (UTT).\n\n"
            "Nhiệm vụ của mình là hỗ trợ bạn giải đáp nhanh chóng và chuẩn xác các thắc mắc về:\n"
            "- Quy chế đào tạo tín chỉ, đăng ký học phần, thi lại và học lại.\n"
            "- Tiêu chuẩn xét học bổng khuyến khích học tập, miễn giảm học phí và trợ cấp xã hội.\n"
            "- Hướng dẫn đánh giá điểm rèn luyện sinh viên theo 5 tiêu chí.\n"
            "- Nội quy Ký túc xá, thủ tục mượn sách Thư viện, dịch vụ hành chính điện tử.\n"
            "- Khung chương trình đào tạo và đề cương chi tiết các môn học ngành Công nghệ Thông tin (K73).\n\n"
            "Bạn đang cần tìm hiểu thông tin gì? Cứ nhắn cho mình nhé!"
        )
        
    # 2. Hoi ve chuc nang / nang luc cua Bot
    if re.search(r"\b(bạn có thể làm gì|bạn giúp được gì|chức năng của bạn|hướng dẫn sử dụng bot|bạn làm được gì)\b", q):
        return (
            "UTee có thể hỗ trợ bạn tra cứu mọi quy chế, quy định và thông tin học vụ tại UTT:\n"
            "1. Quy chế đào tạo: Đăng ký tín chỉ, thang điểm, học phần tiên quyết, điều kiện tốt nghiệp.\n"
            "2. Học bổng & Học phí: Mức học bổng Khá/Giỏi/Xuất sắc, thời hạn đóng học phí.\n"
            "3. Điểm rèn luyện: Cách tính điểm, quy trình xét duyệt qua GVCN và Đoàn/Hội.\n"
            "4. Tiện ích & Đời sống: Ký túc xá, mượn sách thư viện, CLB sinh viên.\n"
            "5. Đề cương học phần: Mục tiêu, số tín chỉ và nội dung chi tiết các môn CNTT.\n\n"
            "Bạn chỉ cần gõ câu hỏi tự nhiên bằng tiếng Việt, mình sẽ tìm văn bản gốc và trích dẫn số Điều, số Trang cụ thể cho bạn!"
        )
        
    # 3. Loi chao don thuan
    if re.search(r"^(xin chào|chào bạn|chào utee|hello|hi|hey|chào)\b", q) and len(q.split()) <= 4:
        return "Chào bạn! Mình là UTee, trợ lý AI của sinh viên UTT. Hôm nay bạn cần mình hỗ trợ tra cứu quy chế, học bổng hay học phần nào không?"

    # 4. Cam on
    if re.search(r"^(cảm ơn|thanks|thank you|ok cảm ơn|cảm ơn bạn|tks)\b", q):
        return "Không có gì đâu nè! Chúc bạn có một ngày học tập thật hiệu quả và đạt kết quả cao tại UTT nhé. Nếu cần tra cứu thêm điều gì, cứ nhắn cho UTee nha!"

    return None


class UteeRagEngine:
    """
    Co che dieu phoi RAG hoan chinh:
    1. Intent Router: Xy ly nhanh loi chao, dinh danh bot.
    2. Retrieval: Tim kiem doan trich tuong dong nhat trong FAISS.
    3. Safe Refusal Gate: Loc theo nguong tin cay (similarity score >= 0.60). Neu khong du can cu -> Tu choi an toan ngay, khong goi LLM de tiet kiem chi phi va chong ao giac.
    4. Generation: Dong goi Context + System Prompt -> Goi Gemini LLM sinh cau tra loi kem trich dan nguon day du.
    """

    def __init__(
        self,
        vectorstore_dir: Optional[Path] = None,
        llm_models: Optional[List[str]] = None,
        confidence_threshold: float = 0.60,
        provider: Optional[str] = None
    ):
        self.confidence_threshold = confidence_threshold
        self.llm_models = llm_models or ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
        
        # 1. Khoi tao va load Vector Store
        base_dir = Path(__file__).resolve().parent.parent
        self.vector_dir = vectorstore_dir or (base_dir / "data" / "vectorstore")
        
        self.vector_store = UteeVectorStore()
        self.vector_store.load(self.vector_dir)
        
        # 2. Xac dinh Provider: 'local' (Ollama tren GPU) hoac 'gemini' (Google Cloud)
        load_dotenv()
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower().strip()
        self.local_model = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:3b")
        self.local_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434")

        # 3. Khoi tao Gemini Client (dung lam chinh hoac fallback khi can)
        self.gemini_client = None
        api_key = None
        for k_name in ["GEMINI_API_KEY4", "GEMINI_API_KEY5", "GEMINI_API_KEY6", "GEMINI_API_KEY7", "GEMINI_API_KEY8", "GEMINI_API_KEY9", "GEMINI_API_KEY10", "GEMINI_API_KEY", "GEMINI_API_KEY2", "GEMINI_API_KEY3"]:
            val = os.getenv(k_name)
            if val and val.strip():
                api_key = val.strip()
                break
                
        if api_key:
            self.gemini_client = genai.Client(api_key=api_key)
        elif self.provider == "gemini":
            raise ValueError("Khong tim thay API key hop le de khoi tao Gemini LLM!")

        print(f"[RAG ENGINE] Che do hoat dong: LLM_PROVIDER = {self.provider.upper()}" + 
              (f" (Model: {self.local_model} qua GPU RTX 5060)" if self.provider in ["local", "ollama"] else " (Gemini Cloud Flash)"))

    def _call_llm(self, prompt: str) -> str:
        """
        Dieu phoi goi LLM: uu tien Local GPU (Ollama) neu duoc cau hinh,
        hoac goi Gemini Cloud API voi co che auto-fallback.
        """
        if self.provider in ["local", "ollama"]:
            return self._call_ollama(prompt)
        return self._call_gemini(prompt)

    def _call_ollama(self, prompt: str) -> str:
        """
        Goi Local LLM qua REST API cua Ollama.
        Tham so num_gpu=99 giup day 100% cac layer vao VRAM cua GPU RTX 5060.
        """
        try:
            payload = {
                "model": self.local_model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 2500,
                    "num_gpu": 99  # Day 100% layer vao GPU VRAM
                }
            }
            resp = requests.post(f"{self.local_url}/api/chat", json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except requests.exceptions.ConnectionError:
            # Neu Ollama chua bat ma co Gemini Client -> tu dong fallback de khong bi crash
            if self.gemini_client:
                print("\n[CANH BAO]: Khong the ket noi Ollama localhost:11434! Tu dong chuyen sang Gemini Cloud API...")
                return self._call_gemini(prompt)
            raise RuntimeError(
                f"Khong the ket noi den Ollama tai {self.local_url}. "
                "Vui long kiem tra xem ung dung Ollama da duoc bat hay chua!"
            )
        except Exception as e:
            if self.gemini_client:
                print(f"\n[CANH BAO]: Loi Local LLM ({e}). Tu dong chuyen sang Gemini Cloud API...")
                return self._call_gemini(prompt)
            raise RuntimeError(f"Loi khi goi Local LLM ({self.local_model}): {e}")

    def _call_gemini(self, prompt: str) -> str:
        """
        Goi LLM Gemini Cloud voi co che Fallback tu dong giua cac model Flash
        de phong truong hop 1 model bi 503 qua tai tam thoi.
        """
        if not self.gemini_client:
            raise RuntimeError("Gemini Client chua duoc khoi tao do thieu GEMINI_API_KEY.")

        last_error = None
        for model_name in self.llm_models:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,  # Nhiet do thap de cau tra loi chuan xac
                        max_output_tokens=3000  # Du khong gian cho cac huong dan dai nhieu buoc
                    )
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_error = e
                continue
                
        raise RuntimeError(f"Khong the goi bat ky Gemini LLM nao trong danh sach ({last_error})")

    def answer_question(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        """
        Hoi dap mot cau hoi hoan chinh qua luong RAG:
        Tra ve Dict gom: query, answer, is_grounded, confidence_score, citations.
        """
        query_clean = query.strip()
        if not query_clean:
            return {
                "query": query,
                "answer": "Ban vui long nhap cau hoi de UTee co the ho tro nhe!",
                "is_grounded": False,
                "confidence_score": 0.0,
                "citations": []
            }

        # BUOC 1: Kiem tra y dinh giao tiep nhanh (Loi chao, Dinh danh)
        quick_answer = detect_quick_intent(query_clean)
        if quick_answer:
            return {
                "query": query_clean,
                "answer": quick_answer,
                "is_grounded": True,
                "confidence_score": 1.0,
                "citations": []
            }

        # BUOC 2: Truy xuat doan trich tuong dong tu FAISS
        search_res = self.vector_store.search(query_clean, top_k=top_k, threshold=self.confidence_threshold)
        matched_chunks = search_res.get("chunks", [])
        
        # BUOC 3: Safe Refusal Gate (Rao chan tu choi an toan)
        if not matched_chunks:
            return {
                "query": query_clean,
                "answer": (
                    "Hien tai UTee chua tim thay thong tin hoac quy dinh chinh thuc nao cua truong UTT "
                    "lien quan den cau hoi nay trong kho tai lieu quy che. "
                    "Ban vui long lien he truc tiep voi Phong Dao tao, Khoa chuyen mon hoac Co van hoc tap "
                    "de duoc huong dan chinh xac nhat nhe!"
                ),
                "is_grounded": False,
                "confidence_score": 0.0,
                "citations": []
            }

        # BUOC 4: Dong goi Ngu canh (Context)
        context_parts = []
        citations = []
        top_score = matched_chunks[0]["similarity_score"]
        
        for idx, chunk in enumerate(matched_chunks, start=1):
            doc_title = chunk.get("doc_title", "Tai lieu UTT")
            section = chunk.get("section", "Quy dinh")
            page = chunk.get("page", 1)
            score = chunk.get("similarity_score", 0.0)
            content = chunk.get("content", "")
            
            context_parts.append(
                f"--- [DOAN TRICH {idx}] (Nguon: {doc_title} | {section} | Trang {page}) ---\n{content}"
            )
            
            citations.append({
                "source_file": chunk.get("source", ""),
                "doc_title": doc_title,
                "category": chunk.get("category", ""),
                "section": section,
                "page": page,
                "similarity_score": round(score, 4)
            })

        full_context = "\n\n".join(context_parts)
        
        prompt = f"""{SYSTEM_PROMPT_TEMPLATE}

[NGU CANH / CONTEXT DUOC TRA CUU TU KHO QUY CHE UTT]:
{full_context}

---
CAU HOI CUA SINH VIEN:
{query_clean}

TRA LOI CUA UTEE (Dua sat vao can cu tren, ro rang va trich dan nguon day du):
"""

        # BUOC 5: Goi LLM tao cau tra loi
        try:
            llm_answer = self._call_llm(prompt)
        except Exception as e:
            llm_answer = f"Da xay ra loi khi ket noi voi mo hinh AI ({e}). Vui long thu lai sau."

        return {
            "query": query_clean,
            "answer": llm_answer,
            "is_grounded": True,
            "confidence_score": round(top_score, 4),
            "citations": citations
        }


def run_interactive_cli():
    """
    Giao dien hoi dap truc tiep tren Terminal de test he thong RAG.
    """
    print("=" * 70)
    print("KHOI DONG HE THONG CHATBOT AI UTEE (RAG ENGINE)")
    print("Dang load Vector Database vao bo nho...")
    
    try:
        engine = UteeRagEngine()
    except Exception as e:
        print(f"[LOI KHOI TAO]: {e}")
        return

    print("=" * 70)
    print("UTee da san sang! Nhap cau hoi cua ban ve truong UTT.")
    print("(Nhap 'exit' hoac 'quit' de thoat)")
    print("=" * 70)
    
    while True:
        try:
            user_input = input("\n[BAN]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\n[UTee]: Tam biet ban! Chuc ban mot ngay hoc tap hieu qua tai UTT.")
                break
                
            print("[UTee]: Dang suy nghi va tra cuu quy che...", flush=True)
            res = engine.answer_question(user_input)
            
            print(f"\n[UTee]:\n{res['answer']}")
            
            # Hien thi danh sach nguon tham khao
            if res["citations"]:
                print("\n[TRICH DAN NGUON]:")
                for c in res["citations"]:
                    print(f"  * {c['doc_title']} - {c['section']} (Trang {c['page']}) [Do tin cay: {c['similarity_score']:.2f}]")
            else:
                if res["confidence_score"] == 1.0:
                    pass  # Cau hoi giao tiep thong thuong, khong can hien thi nguon
                else:
                    print("\n[TRICH DAN NGUON]: (Khong co can cu phu hop - Kich hoat Safe Refusal)")
                
        except (KeyboardInterrupt, EOFError):
            print("\n[UTee]: Da dung chuong trinh.")
            break


if __name__ == "__main__":
    engine = UteeRagEngine()
    
    test_queries = [
        "Bạn là ai?",
        "Hướng dẫn sử dụng hệ thống web daotao và đăng kí tín chỉ"
    ]
    
    print("\n" + "=" * 70)
    print("KIEM THU LAI 2 CAU HOI BAN VUA TEST")
    print("=" * 70)
    
    for q in test_queries:
        print(f"\n>>> CAU HOI: \"{q}\"")
        ans = engine.answer_question(q)
        print(f"[TRANG THAI]: {'CO CAN CU' if ans['is_grounded'] else 'TU CHOI AN TOAN'}")
        print(f"[CAU TRA LOI]:\n{ans['answer']}")
        if ans["citations"]:
            print(f"[SO NGUON TRICH DAN]: {len(ans['citations'])}")
        print("-" * 50)
