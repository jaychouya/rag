import os
import sys

app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from law_finder.tree_flatten import flatten_law_children, rows_for_j1_batch


def test_flatten_parent_path_and_order():
    tree = [
        {
            "pathname": "Doc/第一章",
            "summary": "章摘",
            "children": [
                {
                    "pathname": "Doc/第一章/第1条",
                    "summary": "条摘",
                    "content": "正文",
                }
            ],
        }
    ]
    flat = flatten_law_children(tree)
    assert len(flat) == 2
    assert flat[0]["pathname"] == "Doc/第一章"
    assert flat[0]["parent_pathname"] == ""
    assert flat[1]["pathname"] == "Doc/第一章/第1条"
    assert flat[1]["parent_pathname"] == "Doc/第一章"
    assert flat[1]["is_article"] is True
    j1 = rows_for_j1_batch(flat)
    assert "_ref" not in j1[0]
    assert j1[1]["parent_pathname"] == "Doc/第一章"


def test_ts_query_text():
    from law_finder.retrieval_sql import _ts_query_text

    assert "a" in _ts_query_text("  a  b  ")
    assert len(_ts_query_text("x" * 3000)) <= 2000
