from __future__ import annotations

from pydantic import BaseModel

from chatbot.features.ai.tooling import ToolContract, build_tool_schema
from chatbot.features.billing.tools import BILLING_TOOL_CONTRACTS
from chatbot.features.scheduling.tools import SCHEDULING_TOOL_CONTRACTS

TOOL_CONTRACTS: list[ToolContract] = [
    *BILLING_TOOL_CONTRACTS,
    *SCHEDULING_TOOL_CONTRACTS,
]

TOOL_CONTRACT_BY_NAME: dict[str, ToolContract] = {
    contract.name: contract
    for contract in TOOL_CONTRACTS
}

TOOL_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    contract.name: contract.input_schema
    for contract in TOOL_CONTRACTS
}

TOOL_EXECUTOR_BY_NAME = {
    contract.name: contract.executor
    for contract in TOOL_CONTRACTS
}

OPENAI_TOOL_SCHEMAS = [
    build_tool_schema(contract)
    for contract in TOOL_CONTRACTS
]
