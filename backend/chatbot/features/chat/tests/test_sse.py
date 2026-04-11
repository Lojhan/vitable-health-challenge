from collections.abc import AsyncGenerator

from chatbot.features.chat.sse import single_chunk_response, stream_async_generator, to_sse_chunk


def test_to_sse_chunk_formats_single_line():
    assert to_sse_chunk('hello') == 'data: hello\n\n'


def test_to_sse_chunk_formats_multiple_lines():
    assert to_sse_chunk('line 1\nline 2') == 'data: line 1\ndata: line 2\n\n'


def test_single_chunk_response_returns_sse_bytes():
    assert list(single_chunk_response('hello')) == [b'data: hello\n\n']


def test_stream_async_generator_collects_and_formats_chunks():
    closed = False
    collected: list[str] = []

    async def generator() -> AsyncGenerator[str]:
        yield 'hello'

    async def on_close() -> None:
        nonlocal closed
        closed = True

    def on_complete(chunks) -> None:
        collected.extend(chunks)

    streamed = b''.join(
        stream_async_generator(generator(), on_close=on_close, on_complete=on_complete)
    ).decode()

    assert streamed == 'data: hello\n\n'
    assert closed is True
    assert collected == ['hello']
