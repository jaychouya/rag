import asyncio, json
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config
cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    r = await pg.execute_query("SELECT pathname, body, summary FROM legal_document_node LIMIT 5")
    for row in r:
        print(f"  pathname: {row['pathname'][:80]}")
        print(f"  body: {(row['body'] or '')[:100]}")
        print(f"  summary: {(row['summary'] or '')[:100]}")
        print()

    r2 = await pg.execute_query("SELECT COUNT(*) as n FROM legal_document_node WHERE body IS NOT NULL AND body != ''")
    r3 = await pg.execute_query("SELECT COUNT(*) as n FROM legal_document_node WHERE summary IS NOT NULL AND summary != ''")
    print(f"nodes with body: {r2[0]['n']}")
    print(f"nodes with summary: {r3[0]['n']}")

    doc = await pg.execute_query("SELECT id, name, content FROM LegalDocuments WHERE enabled=TRUE LIMIT 1")
    if doc:
        c = doc[0]["content"]
        if isinstance(c, str):
            c = json.loads(c)
        if isinstance(c, dict):
            keys = list(c.keys())
            print(f"\nDoc '{doc[0]['name']}' top-level keys: {keys}")
            children = c.get("children", [])
            if children:
                ch = children[0]
                print(f"  first child keys: {list(ch.keys())}")
                print(f"  first child sample: {json.dumps(ch, ensure_ascii=False)[:300]}")
                sub = ch.get("children", [])
                if sub:
                    print(f"  first grandchild keys: {list(sub[0].keys())}")
                    print(f"  first grandchild: {json.dumps(sub[0], ensure_ascii=False)[:300]}")

asyncio.run(main())
