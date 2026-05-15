import asyncio
import json
import logging
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


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    async def stream():
        from law_finder.finder import _mode_override, auto_query, get_summary_law_result_prompt
        from law_finder.llm import LLMSDK

        if req.mode:
            _mode_override.set(req.mode.strip().lower())

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
            if not task.done():
                task.cancel()

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
