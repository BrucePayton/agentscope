# -*- coding: utf-8 -*-
"""Bound model waits even when provider adapters swallow cancellation."""
import asyncio
from typing import Any, Awaitable, AsyncGenerator

from ..model import ChatResponse


async def wait_model_result(
    awaitable: Awaitable[Any],
    timeout: float | None,
) -> Any:
    """Cancel and drain an expired call, without mistaking it for success."""
    if timeout is None:
        return await awaitable
    task = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if task in done:
            return task.result()
        raise TimeoutError(f"Model response timed out after {timeout:g}s")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def prime_model_stream(
    stream: AsyncGenerator[ChatResponse, None],
    timeout: float | None,
    first_timeout: float | None,
) -> AsyncGenerator[ChatResponse, None]:
    """Read the first chunk inside the fallback boundary; never replay output."""
    try:
        first = await wait_model_result(anext(stream), first_timeout)
    except BaseException:
        await stream.aclose()
        raise

    async def consume() -> AsyncGenerator[ChatResponse, None]:
        try:
            yield first
            while True:
                try:
                    chunk = await wait_model_result(anext(stream), timeout)
                except StopAsyncIteration:
                    break
                yield chunk
        finally:
            await stream.aclose()

    return consume()
