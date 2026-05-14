import asyncio
import functools
import inspect
from typing import Any, Dict, Literal, Optional


class Tracer:
    def __init__(self, span: Any):
        self.span = span

    async def set_input(self, input: str | dict):
        pass

    async def set_output(self, output: Any):
        pass

    async def add_event(self, event_name: str, event_data: Optional[dict] = None, tag: Optional[str] = None):
        pass

    async def set_attributes(self, attributes: dict):
        pass

    async def set_attribute(self, key: str, value: str):
        pass

    async def record_exception(self, exception: BaseException):
        pass


class TracerManager:
    @staticmethod
    def inject_context(dst: dict):
        pass

    @staticmethod
    def extract_context(dst: dict):
        return None

    @staticmethod
    def trace(
        span_name=None,
        project_name: Optional[str] = None,
        parent_context=None,
        kind="chain",
        capture_input=False,
        capture_output=False,
        capture_exception=True,
        exclude_input_arg_types=None,
    ):
        return TracerManager.trace_current(capture_input, capture_output, capture_exception)

    @staticmethod
    def trace_current(capture_input=False, capture_output=False, capture_exception=True):
        def decorator(func):
            if inspect.isasyncgenfunction(func):

                @functools.wraps(func)
                async def async_gen_wrapper(*args, **kwargs):
                    gen = func(*args, **kwargs)
                    async for item in gen:
                        yield item

                return async_gen_wrapper

            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return await func(*args, **kwargs)

                return async_wrapper

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return sync_wrapper

        return decorator

    @staticmethod
    async def set_input(data):
        pass

    @staticmethod
    async def set_output(data):
        pass

    @staticmethod
    async def record_exception(exception):
        pass

    @staticmethod
    async def add_event(event, event_data: Optional[dict] = None, tag: Optional[str] = None):
        pass
