import asyncio, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, "app")
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

from law_finder.retrieval_sql import _extract_cn_keywords, try_search_document_ids

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    tests = [
        "案件简述 员工被其雇主老板拖欠劳动报酬 形成劳资之间的债权债务纠纷 劳动合同 劳动仲裁 民事债权 用人单位责任",
        "邻居装修噪音扰民怎么处理",
    ]
    for q in tests:
        kws = _extract_cn_keywords(q)
        print(f"\nQ: {q[:30]}...")
        print(f"  keywords: {kws}")
        ids = await try_search_document_ids(q)
        print(f"  FTS docs ({len(ids or [])}): {ids}")
        if ids:
            placeholders = ",".join(str(i) for i in ids[:10])
            rows = await pg.execute_query(f"SELECT id, name FROM LegalDocuments WHERE id IN ({placeholders})")
            for r in rows:
                print(f"    {r['id']}: {r['name']}")

asyncio.run(main())
