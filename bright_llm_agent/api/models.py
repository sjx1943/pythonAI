from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class ChatCompletionDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None

class ChatCompletionChoice(BaseModel):
    index: int
    message: Optional[ChatMessage] = None
    delta: Optional[ChatCompletionDelta] = None
    finish_reason: Optional[str] = "stop"

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage

class ErrorResponse(BaseModel):
    error: Dict[str, Any] 