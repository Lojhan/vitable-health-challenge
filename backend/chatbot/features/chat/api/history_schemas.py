from ninja import Schema


class ChatMessageResponseSchema(Schema):
    role: str
    message_kind: str
    content: str
    created_at: str


class ChatSessionResponseSchema(Schema):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessageResponseSchema]


class ChatSessionSummarySchema(Schema):
    id: int
    title: str
    created_at: str
    updated_at: str


class ChatHistoryResponseSchema(Schema):
    sessions: list[ChatSessionSummarySchema]
    next_cursor: str | None
    has_more: bool


class ChatHistorySyncSchema(Schema):
    latest_updated_at: str | None
    session_count: int
    message_count: int


class ErrorDetailSchema(Schema):
    detail: str