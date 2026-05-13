"""
KubeMind — Retry Handling Utility
Implements exponential backoff for failed microservice communication.
"""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, Type

logger = logging.getLogger("kubemind.retry")


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,),
    fallback: Optional[Any] = None,
) -> Any:
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
                await asyncio.sleep(delay)
    logger.error(f"All {max_retries + 1} retries failed: {last_exc}")
    if fallback is not None:
        return fallback() if callable(fallback) else fallback
    raise last_exc


class RetryHandler:
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5, max_delay: float = 10.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def call(self, func: Callable, fallback: Optional[Any] = None) -> Any:
        return await retry_async(func, self.max_retries, self.base_delay, self.max_delay, fallback=fallback)


retry_handler = RetryHandler()
