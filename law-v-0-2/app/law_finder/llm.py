# 使用豆包做summary
import contextvars
import os

from law_compat.openai_sdk import OpenAICompatibleSDK

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

_request_llm: contextvars.ContextVar[OpenAICompatibleSDK | None] = contextvars.ContextVar(
    "law_finder_request_llm", default=None
)

_default_llm = OpenAICompatibleSDK(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL)


def replace_default_llm(sdk: OpenAICompatibleSDK) -> None:
    global _default_llm
    _default_llm = sdk


class _LLMDelegate:
    __slots__ = ()

    def _t(self) -> OpenAICompatibleSDK:
        x = _request_llm.get()
        return x if x is not None else _default_llm

    def __getattr__(self, name):
        return getattr(self._t(), name)


LLMSDK = _LLMDelegate()


def set_request_llm(sdk: OpenAICompatibleSDK | None):
    return _request_llm.set(sdk)


def reset_request_llm(token) -> None:
    _request_llm.reset(token)


__ALL__ = [
    "LLMSDK",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "replace_default_llm",
    "set_request_llm",
    "reset_request_llm",
]
