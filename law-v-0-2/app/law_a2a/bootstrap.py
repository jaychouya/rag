import logging
import os
from pathlib import Path

import uvicorn
import yaml

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from fastapi import FastAPI

from law_compat.env_yaml import process_env_vars


def _load_agent_conf(config_dir: Path) -> dict:
    p = config_dir / "agent_conf.yml"
    with open(p, encoding="utf-8") as f:
        return process_env_vars(yaml.safe_load(f))


def _build_agent_card(config_dir: Path, cfg: dict) -> AgentCard:
    p = config_dir / "a2a_card.yml"
    with open(p, encoding="utf-8") as f:
        d = process_env_vars(yaml.safe_load(f))
    server_url = d.get("url")
    if not server_url:
        raise ValueError("a2a_card.yml 缺少 url")
    skills = []
    for sk in d.get("skills", []):
        skills.append(
            AgentSkill(
                id=sk["id"],
                name=sk["name"],
                description=sk["description"],
                tags=sk.get("tags", []),
                examples=sk.get("examples", []),
                input_modes=sk.get("input_modes", ["text/plain"]),
                output_modes=sk.get("output_modes", ["text/plain"]),
            )
        )
    desc = d.get("description") or cfg.get("agent_description", "")
    return AgentCard(
        name=cfg["agent_name"],
        description=desc,
        url=server_url,
        version=d.get("version", "1.0.0"),
        default_input_modes=d.get("default_input_modes", ["text/plain"]),
        default_output_modes=d.get("default_output_modes", ["application/json", "text/plain"]),
        capabilities=AgentCapabilities(
            streaming=d.get("capabilities", {}).get("streaming", True),
            push_notifications=d.get("capabilities", {}).get("push_notifications", True),
            state_transition_history=d.get("capabilities", {}).get("state_transition_history", False),
        ),
        skills=skills,
        supports_authenticated_extended_card=d.get("supports_authenticated_extended_card", False),
    )


def _apply_llm_from_config(cfg: dict) -> None:
    import law_finder.llm as lf_llm
    from law_compat.openai_sdk import OpenAICompatibleSDK

    lc = cfg["llm_config"]
    lf_llm.LLMSDK = OpenAICompatibleSDK(
        base_url=lc["base_url"],
        model=lc["model"],
        api_key=lc.get("api_key") or "",
        temperature=float(lc.get("temperature", 0.7)),
        max_tokens=lc.get("max_tokens"),
        context_window_len=lc.get("context_window_len", 32768),
        timeout=float(lc.get("timeout", 300)),
    )


def _create_app(config_dir: Path | None = None) -> FastAPI:
    if config_dir is None:
        config_dir = Path(__file__).resolve().parent.parent / "agent.confd"
    cfg = _load_agent_conf(config_dir)
    _apply_llm_from_config(cfg)
    _app = FastAPI()
    from fastapi.middleware.cors import CORSMiddleware
    _app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    from law_a2a.chat_api import router as chat_router
    _app.include_router(chat_router)
    try:
        from law_a2a.executor import LawA2AgentExecutor
        card = _build_agent_card(config_dir, cfg)
        handler = DefaultRequestHandler(
            agent_executor=LawA2AgentExecutor(),
            task_store=InMemoryTaskStore(),
            queue_manager=None,
            push_config_store=None,
            push_sender=None,
            request_context_builder=None,
        )
        A2AStarletteApplication(agent_card=card, http_handler=handler).add_routes_to_app(_app)
    except Exception:
        pass
    return _app


app = _create_app()


def run(config_dir: Path | None = None) -> None:
    if config_dir is None:
        config_dir = Path(__file__).resolve().parent.parent / "agent.confd"
    cfg = _load_agent_conf(config_dir)
    host = os.getenv("SERVER_HOST", cfg.get("server", {}).get("host", "0.0.0.0"))
    port = int(os.getenv("A2A_SERVER_PORT", cfg.get("server", {}).get("port", 80)))
    uvicorn.run(app, host=host, port=port, reload=False)
