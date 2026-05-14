from __future__ import annotations

from typing import Iterable, Optional


def path_matches_parts(path: Optional[str], parts: list[str]) -> bool:
    if not path:
        return False
    return all(p and (p in path) for p in parts)


def recall_at_k(j1_ranked: list[str], gold_groups: list[list[str]], k: int) -> bool:
    head = j1_ranked[:k]
    return all(any(path_matches_parts(p, g) for p in head) for g in gold_groups)


def groups_covered_by_paths(paths: Iterable[Optional[str]], gold_groups: list[list[str]]) -> bool:
    pl = [p or "" for p in paths]
    return all(any(path_matches_parts(p, g) for p in pl) for g in gold_groups)


def any_negative_hit(paths: Iterable[Optional[str]], negatives: list[str]) -> bool:
    for p in paths:
        if not p:
            continue
        for n in negatives:
            if n and n in p:
                return True
    return False


def each_output_matches_some_group(paths: Iterable[Optional[str]], gold_groups: list[list[str]]) -> bool:
    for p in paths:
        if not p:
            continue
        if not any(path_matches_parts(p, g) for g in gold_groups):
            return False
    return True


def final_accuracy_flags(
    returned_paths: list[Optional[str]],
    gold_groups: list[list[str]],
    negatives: list[str],
) -> dict:
    cov = groups_covered_by_paths(returned_paths, gold_groups)
    neg = any_negative_hit(returned_paths, negatives)
    no_extra = each_output_matches_some_group(returned_paths, gold_groups) if returned_paths else False
    strict = bool(cov and not neg and no_extra and returned_paths)
    return {
        "gold_all_hit": cov,
        "no_negative": not neg,
        "no_extra_path": no_extra,
        "strict_ok": strict,
    }
