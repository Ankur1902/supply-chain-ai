from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


class ToolCallTrace(BaseModel):
    tool: str
    input: dict
    result: dict


class ChatResponse(BaseModel):
    conversation_id: int
    message: str
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
