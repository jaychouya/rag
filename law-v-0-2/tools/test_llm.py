import asyncio
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config

cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)
from law_finder.llm import LLMSDK

async def main():
    r = await LLMSDK.chat('Return a JSON object: {"score": 5, "name": "test"}')
    print("response length:", len(r))
    print("response:", repr(r[:300]))

asyncio.run(main())
