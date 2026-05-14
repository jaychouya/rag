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

    legal_terms = "劳动者被用人单位老板拖欠劳动报酬 工资支付义务 劳动合同 劳动监察 劳动仲裁"
    kws = _extract_cn_keywords(legal_terms)
    print(f"legal_terms keywords: {kws}")

    ids = await try_search_document_ids(legal_terms)
    print(f"FTS result ({len(ids or [])}): {ids}")
    if ids:
        placeholders = ",".join(str(i) for i in ids[:15])
        rows = await pg.execute_query(f"SELECT id, name FROM LegalDocuments WHERE id IN ({placeholders})")
        for r in rows:
            print(f"  doc {r['id']}: {r['name']}")

    for kw in ["劳动", "报酬", "工资", "用人", "合同", "仲裁", "监察"]:
        r = await pg.execute_query("SELECT COUNT(DISTINCT document_id) as n FROM legal_document_node WHERE body LIKE $1 OR summary LIKE $1", [f"%{kw}%"])
        print(f"  '{kw}': {r[0]['n']} docs")

asyncio.run(main())
