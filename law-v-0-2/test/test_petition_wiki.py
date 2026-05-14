import asyncio

from law_finder.petition_wiki import petition_wiki_scan, search_petition_wiki


def test_petition_wiki_hit_xinfang():
    hits, _ids = asyncio.run(petition_wiki_scan("我要走信访程序反映问题", limit=5))
    assert len(hits) >= 1
    assert any("信访" in (h.get("title") or "") or "信访" in (h.get("triggers") or "") for h in hits)


def test_petition_wiki_fucha():
    h = asyncio.run(search_petition_wiki("对处理意见不服要申请复查复核", limit=3))
    assert len(h) >= 1
