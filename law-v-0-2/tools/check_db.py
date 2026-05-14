import asyncio
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config

cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    tables = await pg.execute_query("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    print("=== DB tables ===")
    for t in tables:
        print(f"  {t['tablename']}")

    for tbl in ["legal_document_node", "petition_wiki_entry", "legalcategory", "legaldocuments"]:
        try:
            r = await pg.execute_query(f"SELECT COUNT(*) as n FROM {tbl}")
            print(f"\n{tbl}: {r[0]['n']} rows")
        except Exception as e:
            print(f"\n{tbl}: NOT FOUND")

    cats = await pg.execute_query("SELECT COUNT(*) as n FROM LegalCategory")
    docs = await pg.execute_query("SELECT COUNT(*) as n FROM LegalDocuments WHERE enabled=TRUE")
    print(f"\nLegalCategory: {cats[0]['n']} rows")
    print(f"LegalDocuments (enabled): {docs[0]['n']} rows")

asyncio.run(main())
