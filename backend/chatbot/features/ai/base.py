from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, field_validator

from chatbot.features.ai.tool_registry import OPENAI_TOOL_SCHEMAS, TOOL_INPUT_SCHEMAS
from chatbot.features.core.constants import InsuranceTier
from chatbot.features.core.domain.validation import require_non_blank_text


def _strip_and_require_text(value: str, field_name: str) -> str:
    return require_non_blank_text(value, field=field_name)


class UserProfileSchema(BaseModel):
    first_name: str
    insurance_tier: InsuranceTier

    @field_validator('first_name')
    @classmethod
    def validate_first_name(cls: type['UserProfileSchema'], value: str) -> str:
        return _strip_and_require_text(value, 'first_name')


class BaseAgentInterface(ABC):
    TOOL_INPUT_SCHEMAS: ClassVar[dict[str, type[BaseModel]]] = TOOL_INPUT_SCHEMAS

    @classmethod
    def get_tools(cls: type['BaseAgentInterface']) -> list[dict[str, object]]:
        return OPENAI_TOOL_SCHEMAS

    @abstractmethod
    def stream_response(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str]:
        """Stream an AI response for the provided prompt."""

    @classmethod
    def validate_tool_arguments(
        cls: type['BaseAgentInterface'],
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        schema = cls.TOOL_INPUT_SCHEMAS.get(tool_name)
        if schema is None:
            raise ValueError(f'Unsupported tool call: {tool_name}')

        try:
            model = schema.model_validate(arguments)
        except Exception as error:
            raise ValueError(f'Invalid arguments for tool call: {tool_name}') from error

        return model.model_dump(mode='json')
