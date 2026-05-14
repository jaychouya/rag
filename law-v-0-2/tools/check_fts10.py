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

    print("=== 测试1: 纯口语查询(无 direct_keywords) ===")
    q1 = "我被老板欠钱了怎么办"
    kws1 = _extract_cn_keywords(q1)
    print(f"  bigram keywords: {kws1}")
    ids1 = await try_search_document_ids(q1)
    print(f"  FTS results: {len(ids1 or [])} docs")

    print("\n=== 测试2: 纯口语查询 + LLM法律关键词(direct_keywords) ===")
    direct = ["劳动合同", "劳动报酬", "拖欠工资", "劳动关系", "劳动仲裁", "用人单位"]
    ids2 = await try_search_document_ids(q1, direct_keywords=direct)
    print(f"  direct_keywords: {direct}")
    print(f"  FTS results: {len(ids2 or [])} docs")
    if ids2:
        placeholders = ",".join(str(i) for i in ids2[:10])
        rows = await pg.execute_query(f"SELECT id, name FROM LegalDocuments WHERE id IN ({placeholders})")
        for r in rows:
            print(f"    {r['id']}: {r['name']}")

    print("\n=== 测试3: 完全无关查询 ===")
    q3 = "今天天气怎么样"
    ids3 = await try_search_document_ids(q3, direct_keywords=["天气预报", "气象"])
    print(f"  FTS results: {len(ids3 or [])} docs (应该为0)")

    print("\n=== 测试4: 噪音扰民(保持兼容) ===")
    q4 = "邻居装修噪音扰民怎么处理"
    ids4 = await try_search_document_ids(q4, direct_keywords=["噪声污染", "相邻关系", "环境保护"])
    print(f"  FTS results: {len(ids4 or [])} docs")
    if ids4:
        placeholders = ",".join(str(i) for i in ids4[:10])
        rows = await pg.execute_query(f"SELECT id, name FROM LegalDocuments WHERE id IN ({placeholders})")
        for r in rows:
            print(f"    {r['id']}: {r['name']}")

asyncio.run(main())
