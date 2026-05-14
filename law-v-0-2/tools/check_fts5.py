import asyncio, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, "app")
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()
    for kw in ["邻居", "装修", "噪音", "噪声", "扰民", "污染", "环境", "治安", "相邻", "民事"]:
        r = await pg.execute_query("SELECT COUNT(DISTINCT document_id) as n FROM legal_document_node WHERE body LIKE $1 OR summary LIKE $1", [f"%{kw}%"])
        print(f"  '{kw}': {r[0]['n']} docs")

asyncio.run(main())
