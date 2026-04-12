"""
Vercel-style Data Stream Protocol for typed SSE events.

Each line sent over SSE follows the format: ``{prefix}:{json_payload}``

Prefixes:
    0  — text_delta (token-by-token text)
    2  — error
    8  — tool_call (informational, not rendered)
    9  — tool_result (structured UI component)
    d  — finish
    s  — status (loading indicator)
"""

from __future__ import annotations

import json
from typing import Any

PREFIX_TEXT_DELTA = '0'
PREFIX_ERROR = '2'
PREFIX_TOOL_CALL = '8'
PREFIX_TOOL_RESULT = '9'
PREFIX_FINISH = 'd'
PREFIX_STATUS = 's'


def encode_stream_line(prefix: str, payload: Any) -> str:
    """Encode a single protocol line: ``{prefix}:{json}\n``."""
    return f'{prefix}:{json.dumps(payload, default=str, separators=(",", ":"))}\n'


def encode_text_delta(text: str) -> str:
    return encode_stream_line(PREFIX_TEXT_DELTA, text)


def encode_error(message: str) -> str:
    return encode_stream_line(PREFIX_ERROR, message)


def encode_tool_call(
	*,
	tool_call_id: str,
	tool_name: str,
	label: str | None = None,
	phase: str = 'started',
) -> str:
    return encode_stream_line(PREFIX_TOOL_CALL, {
        'tool_call_id': tool_call_id,
        'tool_name': tool_name,
        'label': label,
        'phase': phase,
    })


def encode_tool_result(*, tool_name: str, tool_call_id: str, ui_kind: str, result: Any) -> str:
    return encode_stream_line(PREFIX_TOOL_RESULT, {
        'tool_name': tool_name,
        'tool_call_id': tool_call_id,
        'ui_kind': ui_kind,
        'result': result,
    })


def encode_status(payload: Any) -> str:
    return encode_stream_line(PREFIX_STATUS, payload)


def encode_finish(finish_reason: str = 'stop') -> str:
    return encode_stream_line(PREFIX_FINISH, {'finish_reason': finish_reason})
