import asyncio, sys, io, importlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, "app")
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

from law_finder.retrieval_sql import _extract_cn_keywords, try_search_document_ids

queries = [
    "邻居装修噪音扰民怎么处理",
    "交通事故赔偿标准",
    "劳动合同纠纷如何维权",
    "离婚财产分割问题",
    "物业管理费用纠纷",
]

async def main():
    for q in queries:
        kws = _extract_cn_keywords(q)
        print(f"Q: {q}")
        print(f"  keywords: {kws}")
        ids = await try_search_document_ids(q)
        print(f"  matched doc_ids ({len(ids or [])}): {ids}")
        print()

asyncio.run(main())
