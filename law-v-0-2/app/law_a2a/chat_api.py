import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

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
    show_debug: bool = True


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_llm_required() -> bool:
    v = os.getenv("LAW_CHAT_CLIENT_LLM_REQUIRED", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def _ts() -> str:
    return time.strftime("%H:%M:%S")


@router.post("/chat")
async def chat(req: ChatRequest):
    key = (req.llm_api_key or "").strip()
    if not key:

        async def deny():
            yield _sse(
                {
                    "type": "error",
                    "content": "远程服务不会使用服务端 API Key。请在前端填写你自己的 llm_api_key、llm_base_url、llm_model。",
                }
            )
            yield _sse({"type": "done"})

        return StreamingResponse(deny(), media_type="text/event-stream")

    async def stream():
        from law_compat.openai_sdk import OpenAICompatibleSDK
        from law_finder.finder import _mode_override, auto_query, get_summary_law_result_prompt
        from law_finder import llm as lf_llm
        from law_finder.llm import LLMSDK

        show_debug = req.show_debug
        mode = (req.mode or os.getenv("LAW_FINDER_MODE", "fast")).strip().lower()
        _mode_override.set(mode)

        bu = (req.llm_base_url or lf_llm.LLM_BASE_URL or "").strip()
        md = (req.llm_model or lf_llm.LLM_MODEL or "").strip()
        if not bu or not md:
            yield _sse({"type": "error", "content": "请填写 llm_base_url 与 llm_model（可与 Key 一起保存在前端）。"})
            yield _sse({"type": "done"})
            return
        llm_src = f"仅使用你的 Key | {bu} | {md}"
        token = lf_llm.set_request_llm(OpenAICompatibleSDK(base_url=bu, model=md, api_key=key))

        def dbg(msg: str) -> Optional[str]:
            if not show_debug:
                return None
            return _sse({"type": "debug", "content": f"[{_ts()}] {msg}"})

        if (line := dbg(f"模式={mode} | {llm_src}")):
            yield line

        progress_q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        def cb(msg: str):
            progress_q.put_nowait(("progress", msg.rstrip("\n")))

        task: Optional[asyncio.Task] = None
        try:
            if (line := dbg("开始 auto_query（检索流水线）")):
                yield line
            task = asyncio.create_task(
                auto_query(
                    req.query,
                    category_scope=req.category_scope or None,
                    law_tags=req.law_tags or None,
                    progressCallback=cb,
                )
            )

            _HEARTBEAT_INTERVAL = 15
            while not task.done():
                try:
                    kind, item = await asyncio.wait_for(progress_q.get(), timeout=_HEARTBEAT_INTERVAL)
                    if kind == "progress":
                        yield _sse({"type": "progress", "content": item})
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

            while not progress_q.empty():
                kind, item = progress_q.get_nowait()
                if kind == "progress":
                    yield _sse({"type": "progress", "content": item})

            raw = task.result()
            if isinstance(raw, str):
                yield _sse({"type": "error", "content": raw})
                yield _sse({"type": "done"})
                return

            result, question_type = raw
            qt = question_type.value if hasattr(question_type, "value") else str(question_type)
            if (line := dbg(f"问题类型={qt} | 结果条数={len(result) if isinstance(result, list) else 'n/a'}")):
                yield line
            if isinstance(result, list) and show_debug:
                preview = [{"name": (x.get("name") or x.get("docName") or str(x))[:80]} for x in result[:8]]
                yield _sse({"type": "metrics", "content": json.dumps({"question_type": qt, "result_count": len(result), "preview": preview}, ensure_ascii=False, indent=2)})

            if (line := dbg("开始流式总结（LLM）")):
                yield line
            prompt = get_summary_law_result_prompt(result=result, question=req.query, question_type=question_type)
            async for chunk in LLMSDK.chat_streaming(req.query, prompt):
                yield _sse({"type": "answer", "content": chunk})

            if (line := dbg("完成")):
                yield line
            yield _sse({"type": "done"})
        except Exception as e:
            logging.getLogger(__name__).exception("chat error")
            yield _sse({"type": "error", "content": str(e)})
            if show_debug:
                import traceback as _tb
                yield _sse({"type": "debug", "content": _tb.format_exc()[-2000:]})
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
