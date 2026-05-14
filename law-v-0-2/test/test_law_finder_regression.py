from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from regression_metrics import final_accuracy_flags, recall_at_k

CASES_PATH = Path(__file__).resolve().parent / "law_finder_regression_cases.json"
ROOT = Path(__file__).resolve().parents[1]


def test_regression_cases_schema():
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    assert isinstance(cases, list) and len(cases) >= 1
    for c in cases:
        assert c.get("id")
        assert c.get("law_file")
        assert c.get("case")
        assert isinstance(c.get("gold_path_parts"), list) and c["gold_path_parts"]
        for g in c["gold_path_parts"]:
            assert isinstance(g, list) and g
        assert isinstance(c.get("negative_path_substrings"), list)
        ks = c.get("k_list") or [20]
        assert isinstance(ks, list) and ks
        lf = ROOT / c["law_file"]
        assert lf.is_file(), lf


def test_regression_metrics_pure():
    ranked = ["X/第1条", "X/第2条", "X/第10条"]
    assert recall_at_k(ranked, [["第1条"]], 1)
    assert not recall_at_k(ranked, [["第10条"]], 2)
    assert recall_at_k(ranked, [["第1条"], ["第2条"]], 2)
    flags = final_accuracy_flags(["X/第1条"], [["第1条"]], ["/第10条"])
    assert flags["strict_ok"]
    assert not final_accuracy_flags(["X/第10条"], [["第1条"]], [])["gold_all_hit"]


@pytest.mark.asyncio
async def test_regression_llm_two_stage_vs_legacy():
    if os.getenv("LAW_REGRESSION_LLM", "") != "1":
        pytest.skip("LAW_REGRESSION_LLM=1 且配置 LLM 后跑回归对比")
    app_root = str(ROOT / "app")
    if app_root not in sys.path:
        sys.path.insert(0, app_root)

    from law_finder.find_article_bycase import find_article

    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    report: dict = {"cases": []}
    mp = pytest.MonkeyPatch()
    try:
        for c in cases:
            law_path = ROOT / c["law_file"]
            with open(law_path, encoding="utf-8") as lf:
                raw = json.load(lf)
            content = {"docName": raw["docName"], "children": raw["children"]}
            gold = c["gold_path_parts"]
            negs = c.get("negative_path_substrings") or []
            ks = c.get("k_list") or [20]

            row: dict = {"id": c["id"], "two_stage": {}, "legacy": {}}

            for label, env_legacy in (("two_stage", "0"), ("legacy", "1")):
                mp.setenv("LAW_FINDER_LEGACY_TREE_LLM", env_legacy)
                diag: dict = {}
                out = await find_article(
                    [content],
                    c["case"],
                    max_llm_threads=4,
                    scoreThreshold=3,
                    topK=8,
                    diagnostics_out=diag,
                )
                paths = [x.get("path") for x in out]
                flags = final_accuracy_flags(paths, gold, negs)
                law0 = (diag.get("laws") or [{}])[0]
                j1 = law0.get("j1_ranked_pathnames") or []
                recall = {f"R@{k}": recall_at_k(j1, gold, k) for k in ks}
                row[label] = {
                    "recall_j1": recall,
                    "final_flags": flags,
                    "returned_paths": paths,
                }

            report["cases"].append(row)
    finally:
        mp.undo()

    out_path = ROOT / "test" / "law_finder_regression_last_run.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if os.getenv("LAW_REGRESSION_STRICT", "") == "1":
        for block in report["cases"]:
            assert block["two_stage"]["final_flags"]["strict_ok"], block
            assert block["legacy"]["final_flags"]["strict_ok"], block
