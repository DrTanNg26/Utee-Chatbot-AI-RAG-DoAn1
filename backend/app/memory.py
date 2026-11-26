"""
memory.py - Quan ly lich su hoi thoai trong PostgreSQL (PostgresChatMessageHistory).
Ke thua truc tiep app/memory.py cua repo NCKH va nang cap ho tro:
- Quan ly theo conversation_id & user_id
- Luu kem sources (citations RAG), structured_data (Rich Data Cards), intent, latency_ms
- Cua so truot ngu canh (Sliding Context Window: 3-5 luot hoi thoai gan nhat) de hieu cau hoi tiep noi.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import asc, desc

from app.config.database import SessionLocal
from app.models import Conversation, Message


class PostgresChatMessageHistory:
    def __init__(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ):
        self.db = SessionLocal()
        self.user_uuid: Optional[uuid.UUID] = self._parse_uuid(user_id)
        self.conversation_uuid: Optional[uuid.UUID] = self._parse_uuid(conversation_id)

    @staticmethod
    def _parse_uuid(val: Optional[str]) -> Optional[uuid.UUID]:
        if not val:
            return None
        try:
            return uuid.UUID(str(val))
        except (ValueError, TypeError):
            return None

    def ensure_conversation(self, first_message_hint: str = "Cuộc trò chuyện mới") -> uuid.UUID:
        """Lay hoac tao moi Conversation hop le (kiem tra quyen so huu user_id neu co)."""
        if self.conversation_uuid:
            conv = self.db.query(Conversation).filter(Conversation.id == self.conversation_uuid).first()
            if conv:
                if self.user_uuid is None or conv.user_id is None or conv.user_id == self.user_uuid:
                    return conv.id

        title = (first_message_hint or "Cuộc trò chuyện mới").strip()
        if len(title) > 65:
            title = title[:62] + "..."

        new_conv = Conversation(
            user_id=self.user_uuid,
            title=title or "Cuộc trò chuyện mới",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(new_conv)
        self.db.commit()
        self.db.refresh(new_conv)
        self.conversation_uuid = new_conv.id
        return new_conv.id

    def add_user_message(self, text: str) -> Message:
        conv_id = self.ensure_conversation(first_message_hint=text)
        msg = Message(
            conversation_id=conv_id,
            user_id=self.user_uuid,
            role="user",
            message=text,
        )
        conv = self.db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def add_ai_message(
        self,
        text: str,
        intent: Optional[str] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        structured_data: Optional[List[Dict[str, Any]]] = None,
        latency_ms: Optional[float] = None,
    ) -> Message:
        conv_id = self.ensure_conversation()
        msg = Message(
            conversation_id=conv_id,
            user_id=self.user_uuid,
            role="assistant",
            message=text,
            intent=intent,
            sources=sources or [],
            structured_data=structured_data or [],
            latency_ms=latency_ms,
        )
        conv = self.db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        q = self.db.query(Message)
        if self.conversation_uuid:
            q = q.filter(Message.conversation_id == self.conversation_uuid)
        elif self.user_uuid:
            q = q.filter(Message.user_id == self.user_uuid)
        else:
            return []

        q = q.order_by(asc(Message.created_at), asc(Message.id))
        if limit:
            q = q.limit(limit)

        rows = q.all()
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.message,
                "intent": r.intent,
                "sources": r.sources or [],
                "cards": r.structured_data or [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def get_recent_window(self, max_turns: int = 4) -> List[Dict[str, str]]:
        """
        Lay N luot hoi dap gan nhat trong phien de LLM hieu cau hoi tiep noi
        (vd: 'Còn tuần sau thì sao?', 'Thế điều kiện loại Giỏi là bao nhiêu?') ma khong ton token.
        """
        q = self.db.query(Message)
        if self.conversation_uuid:
            q = q.filter(Message.conversation_id == self.conversation_uuid)
        elif self.user_uuid:
            q = q.filter(Message.user_id == self.user_uuid)
        else:
            return []

        rows = (
            q.order_by(desc(Message.created_at), desc(Message.id))
            .limit(max_turns * 2)
            .all()
        )
        rows.reverse()
        return [{"role": r.role, "content": r.message[:450]} for r in rows]

    def clear(self) -> None:
        if self.conversation_uuid:
            self.db.query(Message).filter(Message.conversation_id == self.conversation_uuid).delete()
        elif self.user_uuid:
            self.db.query(Message).filter(Message.user_id == self.user_uuid).delete()
        self.db.commit()

    def close(self) -> None:
        self.db.close()
