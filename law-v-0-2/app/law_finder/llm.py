# 使用豆包做summary
import os

from law_compat.openai_sdk import OpenAICompatibleSDK

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

LLMSDK = OpenAICompatibleSDK(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL)
__ALL__ = ["LLMSDK"]