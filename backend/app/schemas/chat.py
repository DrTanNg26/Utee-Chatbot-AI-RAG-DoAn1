from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """
    Ho tro dong thoi ca 3 dinh dang payload tu Frontend:
    1. Chuan UTee Spec: {"message": "...", "conversation_id": "..."}
    2. Chuan query don gian: {"query": "..."}
    3. Chuan NCKH Frontend: {"user_query": {"text": "..."}}
    """
    message: Optional[str] = None
    query: Optional[str] = None
    user_query: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None

    def extract_text(self) -> str:
        if self.message and self.message.strip():
            return self.message.strip()
        if self.query and self.query.strip():
            return self.query.strip()
        if isinstance(self.user_query, dict):
            txt = self.user_query.get("text") or self.user_query.get("query") or ""
            if isinstance(txt, str):
                return txt.strip()
        return ""


class CitationDTO(BaseModel):
    doc_id: Optional[int] = None
    source_file: str
    doc_title: str
    category: Optional[str] = ""
    section: str = ""
    page: Any = 1
    similarity_score: float = 0.0
    excerpt: Optional[str] = ""


class RichCardDTO(BaseModel):
    card_type: str = Field(..., description="grades | retake_alert | timetable | exams | profile")
    title: str
    summary: Optional[str] = None
    data: Any


class ChatResponsePayload(BaseModel):
    reply: str
    answer: str
    intent: str
    is_grounded: bool
    requires_auth: bool = False
    confidence_score: float = 0.0
    conversation_id: Optional[str] = None
    citations: List[CitationDTO] = []
    cards: List[RichCardDTO] = []
    mascot_emotion: str = "f05"  # Ho tro Live2D Mascot Frontend (f01, f04, f05, f06, f07, f08)
    provider_info: Dict[str, Any] = {}
    latency_ms: float = 0.0
