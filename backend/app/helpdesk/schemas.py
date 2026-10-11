from pydantic import BaseModel, Field

class HelpdeskChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )

class HelpdeskSource(BaseModel):
    id: str
    source_type: str
    title: str
    similarity: float

class HelpdeskChatResponse(BaseModel):
    answer: str
    sources: list[HelpdeskSource]