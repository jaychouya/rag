import asyncio

from law_finder.petition_wiki import petition_wiki_scan
from law_finder.structured_filter import extract_structured_filter


def test_petition_alias_gaozhuang_adds_xinfang_scope():
    s = extract_structured_filter("老百姓告状求解决")
    assert s["active"] is True
    assert "信访" in s["category_scope"]


def test_petition_keywords_fucha_in_map():
    s = extract_structured_filter("我要申请信访复查")
    assert "信访" in s["category_scope"]


def test_petition_wiki_online_layer_hits_seed():
    hits, _ = asyncio.run(petition_wiki_scan("不服信访处理意见申请复查复核", limit=5))
    assert len(hits) >= 1
    titles = " ".join(h.get("title", "") for h in hits)
    assert "复查" in titles or "复核" in titles or "信访" in titles
