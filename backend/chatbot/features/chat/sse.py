import asyncio
import json
import queue
import threading
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
    event loop — no thread bridges required.  This eliminates the buffering
    that occurs when ``stream_async_generator`` runs the async loop in a
    background thread under a sync Django view.
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


def stream_async_generator(
    async_generator: AsyncGenerator[object],
    on_close: Callable[[], Awaitable[None]] | None = None,
    on_complete: Callable[[Iterable[Any]], None] | None = None,
) -> Iterable[bytes]:
    completion_queue: queue.Queue[BaseException] = queue.Queue(maxsize=1)
    stream_queue: queue.Queue[object] = queue.Queue()
    sentinel = object()

    async def produce_chunks() -> None:
        try:
            async for chunk in async_generator:
                stream_queue.put(chunk)
        finally:
            if on_close is not None:
                await on_close()
            stream_queue.put(sentinel)

    def run_producer() -> None:
        try:
            asyncio.run(produce_chunks())
        except BaseException as error:
            completion_queue.put(error)
            stream_queue.put(sentinel)

    producer_thread = threading.Thread(target=run_producer, daemon=True)
    producer_thread.start()

    chunks: list[Any] = []
    while True:
        queued_item = stream_queue.get()
        if queued_item is sentinel:
            break
        chunk = queued_item
        chunks.append(chunk)
        yield to_sse_chunk(chunk).encode()

    producer_thread.join()

    if not completion_queue.empty():
        raise completion_queue.get()

    if on_complete is not None:
        on_complete(chunks)
