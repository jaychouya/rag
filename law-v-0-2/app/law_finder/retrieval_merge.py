import os
from typing import Optional


def merge_retrieval_doc_ids(
    fts_ids: Optional[list[int]],
    struct_ids: list[int],
    wiki_ids: list[int],
) -> list[int]:
    mode = (os.getenv("LAW_FINDER_RETRIEVAL_DOC_MERGE_MODE", "union") or "union").strip().lower()
    fs = [int(x) for x in (fts_ids or []) if x is not None]
    st = [int(x) for x in struct_ids if x is not None]
    wk = [int(x) for x in wiki_ids if x is not None]
    s_fs = set(fs)
    s_st = set(st)
    s_wk = set(wk)
    side = s_st | s_wk
    if mode == "intersect":
        if s_fs and side:
            return list(dict.fromkeys([*s_fs & side]))
        if side:
            return list(dict.fromkeys([*side]))
        return list(dict.fromkeys([*s_fs]))
    return list(dict.fromkeys([*s_fs, *s_st, *s_wk]))
