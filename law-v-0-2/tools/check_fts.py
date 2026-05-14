import asyncio
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    q = "邻居装修噪音扰民怎么处理"
    r1 = await pg.execute_query(
        "SELECT COUNT(*) as n FROM legal_document_node WHERE search_vector @@ plainto_tsquery('simple', $1)",
        [q]
    )
    print(f"tsquery match count: {r1[0]['n']}")

    r2 = await pg.execute_query(
        "SELECT COUNT(*) as n FROM legal_document_node WHERE body LIKE '%噪音%'"
    )
    print(f"LIKE '噪音' match count: {r2[0]['n']}")

    r3 = await pg.execute_query(
        "SELECT COUNT(*) as n FROM legal_document_node WHERE body LIKE '%扰民%'"
    )
    print(f"LIKE '扰民' match count: {r3[0]['n']}")

    r4 = await pg.execute_query(
        "SELECT DISTINCT document_id FROM legal_document_node WHERE body LIKE '%噪音%' OR body LIKE '%扰民%'"
    )
    print(f"LIKE match distinct docs: {len(r4)} -> {[x['document_id'] for x in r4]}")

asyncio.run(main())
