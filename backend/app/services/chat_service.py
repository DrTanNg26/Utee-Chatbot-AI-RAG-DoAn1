"""
chat_service.py - Xu ly API hoi thoai, quan ly phien cookie khach (/ck ke thua NCKH),
SSE Streaming va quan ly danh sach lich su cuoc tro chuyen cua sinh vien.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.util import get_current_user, get_optional_user
from app.config.database import get_db
from app.models import Conversation, Message, User
from app.qa_engine import process_query
from app.schemas.chat import ChatMessageRequest

v1_chat_router = APIRouter(prefix="/api/v1/chat", tags=["Chat & Conversations (v1)"])


def _resolve_guest_cookie_user(request: Request, db: Session) -> Optional[str]:
    """Lay va dam bao user_id tu cookie khach ton tai trong bang users (ke thua NCKH)."""
    cookie_uid = request.cookies.get("user_id")
    if not cookie_uid:
        return None
    try:
        parsed_uuid = uuid.UUID(str(cookie_uid))
    except ValueError:
        return None

    user = db.query(User).filter(User.id == parsed_uuid).first()
    if not user:
        user = User(
            id=parsed_uuid,
            username=f"guest_{parsed_uuid.hex[:10]}",
            role="guest",
            is_active=True,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
    else:
        user.last_seen = datetime.now(timezone.utc)
        db.commit()
    return str(parsed_uuid)


def assign_cookie(response: Response, request: Request, db: Session) -> dict:
    """Ke thua endpoint GET /ck cua repo NCKH: Cap cookie user_id cho khach chua dang nhap."""
    try:
        cookie_uid = request.cookies.get("user_id")
        valid_uuid: Optional[uuid.UUID] = None
        if cookie_uid:
            try:
                valid_uuid = uuid.UUID(str(cookie_uid))
            except ValueError:
                valid_uuid = None

        if valid_uuid is None:
            valid_uuid = uuid.uuid4()
            response.set_cookie(
                key="user_id",
                value=str(valid_uuid),
                max_age=60 * 60 * 24 * 7,
                httponly=True,
                samesite="lax",
            )

        user = db.query(User).filter(User.id == valid_uuid).first()
        if not user:
            user = User(
                id=valid_uuid,
                username=f"guest_{valid_uuid.hex[:10]}",
                role="guest",
                is_active=True,
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
            )
            db.add(user)
        else:
            user.last_seen = datetime.now(timezone.utc)
        db.commit()

        return {
            "EC": 0,
            "EM": "Success assign cookie!",
            "DT": {"guest_id": str(valid_uuid)},
        }
    except Exception as exc:
        db.rollback()
        return {
            "EC": 1,
            "EM": f"Something wrong in chat service: {exc}",
            "DT": "",
        }


async def chat_legacy_nckh(
    request: Request,
    db: Session,
    current_user: Optional[User] = None,
) -> dict:
    """
    Xu ly POST /chat tuong thich 100% voi dinh dang repo NCKH ({EC, EM, DT})
    dong thoi kem theo metadata day du (reply, citations, cards, conversation_id).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    parsed = ChatMessageRequest(**body) if isinstance(body, dict) else ChatMessageRequest()
    user_text = parsed.extract_text()
    guest_uid = None if current_user else _resolve_guest_cookie_user(request, db)

    result = process_query(
        user_query=user_text,
        db=db,
        current_user=current_user,
        guest_cookie_user_id=guest_uid,
        conversation_id=parsed.conversation_id,
    )

    return {
        "EC": 0,
        "EM": "Success",
        "DT": result["answer"],
        "data": result,
        **result,
    }


@v1_chat_router.post("/message")
def post_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Endpoint chinh theo Dac ta Ky thuat UTee: POST /api/v1/chat/message."""
    user_text = payload.extract_text()
    guest_uid = None if current_user else _resolve_guest_cookie_user(request, db)

    result = process_query(
        user_query=user_text,
        db=db,
        current_user=current_user,
        guest_cookie_user_id=guest_uid,
        conversation_id=payload.conversation_id,
    )
    return {
        "EC": 0,
        "EM": "Success",
        "DT": result,
        **result,
    }


@v1_chat_router.post("/stream")
async def stream_chat_message(
    payload: ChatMessageRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint SSE Streaming (Server-Sent Events) phuc vu hieu ung go chu thoi gian thuc tren Frontend
    (Dac ta Phan 1.1A). Gui lan luot cac chunk text va ket thuc bang event 'done' chua citations & cards.
    """
    user_text = payload.extract_text()
    guest_uid = None if current_user else _resolve_guest_cookie_user(request, db)

    result = process_query(
        user_query=user_text,
        db=db,
        current_user=current_user,
        guest_cookie_user_id=guest_uid,
        conversation_id=payload.conversation_id,
    )

    async def event_generator():
        words = result["answer"].split(" ")
        step = 3
        for i in range(0, len(words), step):
            token_piece = " ".join(words[i : i + step])
            if i + step < len(words):
                token_piece += " "
            yield f"data: {json.dumps({'type': 'token', 'content': token_piece}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.015)

        final_meta = {
            "type": "done",
            **result,
        }
        yield f"data: {json.dumps(final_meta, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@v1_chat_router.get("/conversations")
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lay danh sach lich su cac cuoc tro chuyen cua chinh user hien tai (Sidebar Chat)."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(desc(Conversation.updated_at))
        .all()
    )
    items = [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]
    return {"EC": 0, "EM": "Lấy danh sách hội thoại thành công!", "DT": items}


@v1_chat_router.get("/history/{conversation_id}")
def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lay toan bo tin nhan trong 1 phien hoi thoai (Kiem tra chat quyen so huu user_id!)."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã phiên hội thoại không hợp lệ.")

    conv = db.query(Conversation).filter(Conversation.id == conv_uuid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại.")
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Truy cập bị từ chối: Bạn không có quyền xem lịch sử hội thoại của người khác.",
        )

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return {
        "EC": 0,
        "EM": "Lấy chi tiết lịch sử hội thoại thành công!",
        "DT": {
            "conversation": {
                "id": str(conv.id),
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
            },
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.message,
                    "intent": m.intent,
                    "citations": m.sources or [],
                    "cards": m.structured_data or [],
                    "latency_ms": m.latency_ms,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ],
        },
    }


@v1_chat_router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã phiên hội thoại không hợp lệ.")

    conv = db.query(Conversation).filter(Conversation.id == conv_uuid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại.")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa hội thoại của người khác.")

    db.delete(conv)
    db.commit()
    return {"EC": 0, "EM": "Đã xóa cuộc trò chuyện thành công!", "DT": {"id": conversation_id}}
