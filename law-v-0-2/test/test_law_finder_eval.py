import json
import os
import sys
import time

import pytest

CASES_PATH = os.path.join(os.path.dirname(__file__), "law_finder_eval_cases.json")


def test_eval_cases_file_schema():
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    assert isinstance(cases, list) and len(cases) >= 1
    for c in cases:
        assert "id" in c
        assert "query" in c


@pytest.mark.asyncio
async def test_auto_query_law_list_smoke():
    if os.getenv("LAW_TEST_EVAL", "") != "1":
        pytest.skip("LAW_TEST_EVAL=1 with LLM+PG 可跑端到端")
    pytest.importorskip("asyncpg")
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
    if app_root not in sys.path:
        sys.path.insert(0, app_root)

    from law_finder.finder import auto_query

    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    law_list = [c for c in cases if c.get("question_type") == "law_list"]
    if not law_list:
        pytest.skip("no law_list case")
    c = law_list[0]
    t0 = time.perf_counter()
    out, qtype = await auto_query(c["query"], category_scope=None, law_tags=None, max_llm_threads=2)
    dt = (time.perf_counter() - t0) * 1000.0
    assert qtype.value == "law_list"
    assert isinstance(out, list)
    assert len(out) >= c.get("min_results", 0)
    assert dt < 600000.0
