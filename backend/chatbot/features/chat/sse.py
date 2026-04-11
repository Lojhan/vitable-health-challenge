import asyncio
import queue
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable


def to_sse_chunk(chunk: str) -> str:
    lines = chunk.splitlines() or ['']
    data_lines = [f'data: {line}' for line in lines]
    return '\n'.join(data_lines) + '\n\n'


def single_chunk_response(chunk: str) -> Iterable[bytes]:
    return [to_sse_chunk(chunk).encode()]


def stream_async_generator(
    async_generator: AsyncGenerator[str],
    on_close: Callable[[], Awaitable[None]] | None = None,
    on_complete: Callable[[Iterable[str]], None] | None = None,
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

    chunks: list[str] = []
    while True:
        queued_item = stream_queue.get()
        if queued_item is sentinel:
            break
        chunk = str(queued_item)
        chunks.append(chunk)
        yield to_sse_chunk(chunk).encode()

    producer_thread.join()

    if not completion_queue.empty():
        raise completion_queue.get()

    if on_complete is not None:
        on_complete(chunks)
