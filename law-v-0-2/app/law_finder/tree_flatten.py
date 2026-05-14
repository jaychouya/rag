def flatten_law_children(lawparts: list[dict]) -> list[dict]:
    rows: list[dict] = []

    def walk(nlist: list[dict], parent_pathname: str) -> None:
        for node in nlist:
            idx = len(rows)
            pathname = node.get("pathname", "") or ""
            summary = node.get("summary") or ""
            scenario = node.get("scenarios_summary") or node.get("scenario") or ""
            rows.append(
                {
                    "idx": idx,
                    "pathname": pathname,
                    "parent_pathname": parent_pathname or "",
                    "summary": summary,
                    "scenario": scenario,
                    "is_article": bool(node.get("content")),
                    "_ref": node,
                }
            )
            ch = node.get("children") or []
            if ch:
                walk(ch, pathname or parent_pathname)

    walk(lawparts or [], "")
    return rows


def rows_for_j1_batch(rows: list[dict]) -> list[dict]:
    return [
        {
            "idx": r["idx"],
            "pathname": r["pathname"],
            "parent_pathname": r.get("parent_pathname", ""),
            "summary": r["summary"],
            "scenario": r["scenario"],
            "is_article": r["is_article"],
        }
        for r in rows
    ]
