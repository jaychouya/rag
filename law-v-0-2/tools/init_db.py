import asyncio
from pathlib import Path
from law_a2a.bootstrap import _load_agent_conf, _apply_llm_from_config

cfg = _load_agent_conf(Path("app/agent.confd"))
_apply_llm_from_config(cfg)

MIGRATIONS = [
    "app/law_finder/migrations/001_legal_document_node.sql",
    "app/law_finder/migrations/002_petition_wiki_entry.sql",
    "app/law_finder/migrations/003_petition_wiki_meta.sql",
]

async def main():
    from law_finder.db_pool import get_shared_pg
    pg = await get_shared_pg()

    for path in MIGRATIONS:
        sql = Path(path).read_text(encoding="utf-8")
        try:
            async with pg.get_connection() as conn:
                await conn.execute(sql)
            print(f"OK: {path}")
        except Exception as e:
            print(f"SKIP: {path} ({e})")

    print("\n--- Populating legal_document_node from LegalDocuments.content ---")
    docs = await pg.execute_query("SELECT id, name, content FROM LegalDocuments WHERE enabled=TRUE AND content IS NOT NULL")
    print(f"Found {len(docs)} enabled documents with content")

    import json
    inserted = 0
    for doc in docs:
        content = doc["content"]
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if not isinstance(content, dict):
            continue
        children = content.get("children", [])
        if not children:
            continue
        nodes = _flatten(children, doc["id"], "")
        for node in nodes:
            try:
                async with pg.get_connection() as conn:
                    await conn.execute("""
                        INSERT INTO legal_document_node (document_id, pathname, unit, node_index, summary, body, search_vector)
                        VALUES ($1, $2, $3, $4, $5, $6, to_tsvector('simple', $7))
                        ON CONFLICT DO NOTHING
                    """, node["doc_id"], node["pathname"], node.get("unit"), node.get("index"),
                        node.get("summary", ""), node.get("body", ""),
                        " ".join(filter(None, [node["pathname"], node.get("summary", ""), node.get("body", "")[:500]])))
                    inserted += 1
            except Exception as e:
                print(f"  insert err: {e}")
    print(f"Inserted {inserted} nodes")

    r = await pg.execute_query("SELECT COUNT(*) as n FROM legal_document_node")
    print(f"legal_document_node total: {r[0]['n']}")

def _flatten(children, doc_id, prefix):
    nodes = []
    for child in children:
        if not isinstance(child, dict):
            continue
        name = child.get("partname") or child.get("name") or ""
        idx = child.get("index")
        unit = child.get("unit")
        path = f"{prefix}/{name}" if prefix else name
        if idx and unit:
            path = f"{prefix}/第{idx}{unit}" if prefix else f"第{idx}{unit}"
        summary = child.get("summary") or child.get("scenarios_summary") or ""
        body = ""
        if "content" in child and isinstance(child["content"], str):
            body = child["content"]
        nodes.append({"doc_id": doc_id, "pathname": path, "unit": unit, "index": str(idx) if idx else None, "summary": summary, "body": body})
        sub = child.get("children", [])
        if sub:
            nodes.extend(_flatten(sub, doc_id, path))
    return nodes

asyncio.run(main())
