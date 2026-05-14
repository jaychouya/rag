import asyncio, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    kw = "噪音"
    r = await pg.execute_query(f"SELECT COUNT(*) as n FROM legal_document_node WHERE body LIKE $1", [f"%{kw}%"])
    print(f"LIKE '%{kw}%' body: {r[0]['n']}")

    r2 = await pg.execute_query(f"SELECT COUNT(*) as n FROM legal_document_node WHERE summary LIKE $1", [f"%{kw}%"])
    print(f"LIKE '%{kw}%' summary: {r2[0]['n']}")

    r3 = await pg.execute_query(f"SELECT COUNT(*) as n FROM legal_document_node WHERE pathname LIKE $1", [f"%{kw}%"])
    print(f"LIKE '%{kw}%' pathname: {r3[0]['n']}")

    r4 = await pg.execute_query("SELECT body FROM legal_document_node WHERE body IS NOT NULL AND LENGTH(body) > 10 LIMIT 1")
    if r4:
        sample = r4[0]["body"][:200]
        print(f"sample body (first 200 chars): {sample}")
        print(f"sample body hex: {sample[:20].encode('utf-8').hex()}")

    r5 = await pg.execute_query(f"SELECT DISTINCT n.document_id, ld.name FROM legal_document_node n JOIN LegalDocuments ld ON ld.id=n.document_id WHERE n.body LIKE $1 OR n.summary LIKE $1 LIMIT 10", [f"%{kw}%"])
    print(f"docs with '{kw}': {len(r5)}")
    for row in r5:
        print(f"  doc {row['document_id']}: {row['name']}")

    kws = ["扰民", "装修", "治安", "刑法", "民法"]
    for k in kws:
        r = await pg.execute_query(f"SELECT COUNT(*) as n FROM legal_document_node WHERE body LIKE $1 OR summary LIKE $1", [f"%{k}%"])
        print(f"  '{k}': {r[0]['n']} nodes")

asyncio.run(main())
