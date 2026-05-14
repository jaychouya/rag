import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))


def _ts_src(pathname: str, summary: str, body: str) -> str:
    b = (body or "")[:2000]
    return f"{pathname or ''} {summary or ''} {b}"


async def _insert_node(pg, doc_id, parent_id, pathname, unit, node_index, summary, body):
    ts = _ts_src(pathname, summary, body)
    row = await pg.execute_query(
        """
        INSERT INTO legal_document_node
            (document_id, pathname, unit, node_index, summary, body, parent_id, search_vector)
        VALUES ($1, $2, $3, $4, $5, $6, $7, to_tsvector('simple', $8))
        RETURNING id
        """,
        [doc_id, pathname or "", unit, node_index, summary or "", body or "", parent_id, ts],
        fetch_mode="one",
    )
    return int(row["id"]) if row and row.get("id") is not None else None


async def _walk(pg, doc_id, nodes, parent_id, doc_name: str):
    for node in nodes or []:
        pathname = node.get("pathname") or ""
        if not pathname and node.get("name"):
            pathname = f"{doc_name}/{node.get('name', '')}"
        unit = None
        if node.get("categoryName"):
            unit = str(node.get("categoryName"))
        elif node.get("unit"):
            unit = str(node.get("unit"))
        node_index = None
        if node.get("index") is not None:
            node_index = str(node.get("index"))
        summary = node.get("summary") or ""
        body = ""
        c = node.get("content")
        if isinstance(c, str):
            body = c
        elif c is not None:
            body = json.dumps(c, ensure_ascii=False)
        nid = await _insert_node(pg, doc_id, parent_id, pathname, unit, node_index, summary, body)
        ch = node.get("children") or []
        if ch and nid is not None:
            await _walk(pg, doc_id, ch, nid, doc_name)


async def main():
    from law_finder.db_pool import get_shared_pg

    pg = await get_shared_pg()
    await pg.execute_query("DELETE FROM legal_document_node", [], fetch_mode="none")
    try:
        rows = await pg.execute_query("SELECT id, name, content FROM LegalDocuments WHERE enabled = TRUE", [])
    except Exception:
        rows = await pg.execute_query('SELECT id, name, content FROM "LegalDocuments" WHERE enabled = TRUE', [])
    for row in rows or []:
        doc_id = int(row["id"])
        doc_name = row.get("name") or ""
        content = row.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                continue
        if not isinstance(content, dict):
            continue
        root_name = content.get("docName") or doc_name
        children = content.get("children") or []
        await _walk(pg, doc_id, children, None, root_name)


if __name__ == "__main__":
    asyncio.run(main())
