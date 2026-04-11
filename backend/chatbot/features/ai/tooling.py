from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    input_schema: type[BaseModel]
    executor: Callable[[dict[str, Any], int | None], object]


def build_tool_schema(contract: ToolContract) -> dict[str, object]:
    return {
        'type': 'function',
        'function': {
            'name': contract.name,
            'description': contract.description,
            'parameters': contract.input_schema.model_json_schema(),
        },
    }
