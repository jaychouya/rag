import os
from typing import Optional

from law_compat.openai_sdk import OpenAICompatibleSDK


def client_llm_required() -> bool:
    v = os.getenv("LAW_CHAT_CLIENT_LLM_REQUIRED", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def parse_client_llm_fields(
    llm_api_key: Optional[str],
    llm_base_url: Optional[str],
    llm_model: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    key = (llm_api_key or "").strip()
    if not key:
        return None, None, None, "请填写 llm_api_key。"
    bu = (llm_base_url or "").strip()
    md = (llm_model or "").strip()
    if not bu or not md:
        return None, None, None, "请填写 llm_base_url 与 llm_model（须与 Key 一并由调用方提供，不会使用服务端地址）。"
    return key, bu, md, None


def make_client_sdk(key: str, bu: str, md: str) -> OpenAICompatibleSDK:
    return OpenAICompatibleSDK(base_url=bu, model=md, api_key=key)
