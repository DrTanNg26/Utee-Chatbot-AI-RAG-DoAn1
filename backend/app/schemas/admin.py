from typing import Any, Dict, Optional
from pydantic import BaseModel


class DocumentDeleteRequest(BaseModel):
    id: int


class DocumentToggleRequest(BaseModel):
    is_active: bool


class ChatbotConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
