import json
import os
import time
from typing import Any, Optional

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


def agent_dbg(hypothesis_id: str, location: str, message: str, data: Optional[dict] = None) -> None:
    payload = {
        "sessionId": "c88a63",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, ensure_ascii=False)
    for p in (
        os.getenv("LAW_DEBUG_LOG", "").strip(),
        "debug-c88a63.log",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "debug-c88a63.log"),
    ):
        if not p:
            continue
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except OSError:
            continue
