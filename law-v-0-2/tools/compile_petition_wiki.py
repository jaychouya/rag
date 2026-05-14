import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


async def upsert_rows(rows: list[dict]) -> int:
    from law_finder.db_pool import get_shared_pg

    pg = await get_shared_pg()
    n = 0
    for r in rows:
        slug = r.get("slug")
        if not slug:
            continue
        await pg.execute_query(
            """
            INSERT INTO petition_wiki_entry
                (slug, title, triggers, actor, action, context, consequence,
                 linked_document_ids, body, effective_from, repealed, source_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::int[], $9, $10, $11, $12)
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                triggers = EXCLUDED.triggers,
                actor = EXCLUDED.actor,
                action = EXCLUDED.action,
                context = EXCLUDED.context,
                consequence = EXCLUDED.consequence,
                linked_document_ids = EXCLUDED.linked_document_ids,
                body = EXCLUDED.body,
                effective_from = EXCLUDED.effective_from,
                repealed = EXCLUDED.repealed,
                source_version = EXCLUDED.source_version,
                updated_at = now()
            """,
            [
                slug,
                r.get("title") or "",
                r.get("triggers") or "",
                r.get("actor"),
                r.get("action"),
                r.get("context"),
                r.get("consequence"),
                r.get("linked_document_ids") or [],
                r.get("body") or "",
                r.get("effective_from"),
                bool(r.get("repealed", False)),
                r.get("source_version"),
            ],
            fetch_mode="none",
        )
        n += 1
    return n


async def run_llm_expand(seed: list[dict]) -> list[dict]:
    from law_finder.jinja_env import get_template
    from law_finder.myextractor import CodeExtractor
    from law_finder.llm import LLMSDK

    tpl = get_template("petition_wiki_compile.jinja2")
    ex = CodeExtractor(llm=LLMSDK, title="petition_wiki_compile")
    out: list[dict] = []
    for row in seed:
        msg = tpl.render(entry=row)
        chunk = await ex.do(message=msg)
        if isinstance(chunk, list) and chunk:
            chunk = chunk[0]
        if isinstance(chunk, dict):
            merged = dict(row)
            for k in ("title", "triggers", "actor", "action", "context", "consequence", "body", "linked_document_ids"):
                if k in chunk and chunk[k] is not None:
                    merged[k] = chunk[k]
            out.append(merged)
        else:
            out.append(row)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=str(ROOT / "app" / "law_finder" / "data" / "petition_wiki_seed.json"))
    ap.add_argument("--llm", action="store_true", help="离线 LLM 扩写条目后再写入库")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    path = Path(args.seed)
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise SystemExit("seed must be a JSON array")
    if args.llm:
        rows = await run_llm_expand(rows)
    if args.dry_run:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    n = await upsert_rows(rows)
    print(f"upserted {n} rows into petition_wiki_entry")


if __name__ == "__main__":
    asyncio.run(main())
