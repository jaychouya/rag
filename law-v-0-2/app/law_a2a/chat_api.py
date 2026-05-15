import asyncio
import json
import logging
import os
import traceback
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    query: str
    mode: Optional[str] = None
    category_scope: Optional[list[str]] = None
    law_tags: Optional[list[str]] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_llm_required() -> bool:
    v = os.getenv("LAW_CHAT_CLIENT_LLM_REQUIRED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


@router.post("/chat")
async def chat(req: ChatRequest):
    if _client_llm_required() and not (req.llm_api_key or "").strip():

        async def deny():
            yield _sse(
                {
                    "type": "error",
                    "content": "本服务未开放公用模型：请在请求中带上您自己的 llm_api_key，或在部署端关闭环境变量 LAW_CHAT_CLIENT_LLM_REQUIRED。",
                }
            )
            yield _sse({"type": "done"})

        return StreamingResponse(deny(), media_type="text/event-stream")

    async def stream():
        from law_compat.openai_sdk import OpenAICompatibleSDK
        from law_finder.finder import _mode_override, auto_query, get_summary_law_result_prompt
        from law_finder import llm as lf_llm
        from law_finder.llm import LLMSDK

        if req.mode:
            _mode_override.set(req.mode.strip().lower())

        token = None
        task = None
        key = (req.llm_api_key or "").strip()
        if key:
            bu = (req.llm_base_url or lf_llm.LLM_BASE_URL or "").strip()
            md = (req.llm_model or lf_llm.LLM_MODEL or "").strip()
            if not bu or not md:
                yield _sse({"type": "error", "content": "使用自带 API 时服务端未配置 LLM_BASE_URL / LLM_MODEL，请联系部署方。"})
                yield _sse({"type": "done"})
                return
            token = lf_llm.set_request_llm(OpenAICompatibleSDK(base_url=bu, model=md, api_key=key))

        progress_q: asyncio.Queue[str] = asyncio.Queue()

        def cb(msg: str):
            progress_q.put_nowait(msg.rstrip("\n"))

        task = asyncio.create_task(
            auto_query(
                req.query,
                category_scope=req.category_scope or None,
                law_tags=req.law_tags or None,
                progressCallback=cb,
            )
        )

        _HEARTBEAT_INTERVAL = 15
        try:
            while not task.done():
                try:
                    item = await asyncio.wait_for(progress_q.get(), timeout=_HEARTBEAT_INTERVAL)
                    yield _sse({"type": "progress", "content": item})
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
            while not progress_q.empty():
                yield _sse({"type": "progress", "content": progress_q.get_nowait()})

            result, question_type = task.result()

            prompt = get_summary_law_result_prompt(result=result, question=req.query, question_type=question_type)
            async for chunk in LLMSDK.chat_streaming(req.query, prompt):
                yield _sse({"type": "answer", "content": chunk})

            yield _sse({"type": "done"})
        except Exception as e:
            import traceback as _tb
            logging.getLogger(__name__).error("chat error: %s", _tb.format_exc())
            yield _sse({"type": "error", "content": str(e)})
            yield _sse({"type": "done"})
        finally:
            if task is not None and not task.done():
                task.cancel()
            if token is not None:
                lf_llm.reset_request_llm(token)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/health")
async def health():
    return {"status": "ok"}


def create_standalone_app():
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config

    cfg = _load_agent_conf(Path(__file__).resolve().parent.parent / "agent.confd")
    _apply_llm_from_config(cfg)

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return app


standalone_app = create_standalone_app()
