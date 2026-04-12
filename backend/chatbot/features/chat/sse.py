import json
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterable
from typing import Any

from asgiref.sync import sync_to_async


def to_sse_chunk(chunk: object) -> str:
    """Wrap a chunk as an SSE ``data:`` frame.

    All payloads are wrapped in ``data:`` lines.
    """
    if isinstance(chunk, str):
        payload = chunk
    else:
        payload = json.dumps(chunk, default=str, separators=(',', ':'))

    lines = payload.splitlines() or ['']
    data_lines = [f'data: {line}' for line in lines]
    return '\n'.join(data_lines) + '\n\n'


def single_chunk_response(chunk: object) -> Iterable[bytes]:
    return [to_sse_chunk(chunk).encode()]


async def stream_response_async(
    async_generator: AsyncGenerator[object],
    on_close: Callable[[], Awaitable[None]] | None = None,
    on_complete: Callable[[Iterable[Any]], None] | None = None,
) -> AsyncIterator[bytes]:
    """Async SSE streaming adapter for Django ASGI ``StreamingHttpResponse``.

    Yields SSE-formatted bytes from *async_generator* directly in the async
    event loop — no thread bridges required.
    """
    chunks: list[Any] = []
    try:
        async for chunk in async_generator:
            chunks.append(chunk)
            yield to_sse_chunk(chunk).encode()
    finally:
        if on_close is not None:
            await on_close()

    if on_complete is not None:
        await sync_to_async(on_complete, thread_sensitive=True)(chunks)
