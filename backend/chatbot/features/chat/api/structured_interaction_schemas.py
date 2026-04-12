from typing import Any

from ninja import Schema


class StructuredInteractionSaveSchema(Schema):
    interaction_id: str
    kind: str
    selection: dict[str, Any]


class StructuredInteractionResponseSchema(Schema):
    interaction_id: str
    selection: dict[str, Any] | None