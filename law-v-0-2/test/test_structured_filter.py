from law_finder.structured_filter import extract_structured_filter


def test_extract_overtime_wage():
    s = extract_structured_filter("我加班没给钱")
    assert s["active"] is True
    assert "其他公共法规" in s["category_scope"]
    assert "社会" in s["tags"] or "劳动" in s["tags"]


def test_extract_assault():
    s = extract_structured_filter("有人把我打伤了")
    assert s["active"] is True
    assert "其他公共法规" in s["category_scope"]
    assert "刑事" in s["tags"]


def test_extract_no_keyword():
    s = extract_structured_filter("今天天气真好")
    assert s["active"] is False
    assert s["category_scope"] == []
    assert s["tags"] == []


def test_longest_phrase_preferred():
    s = extract_structured_filter("拖欠工资怎么办")
    assert "拖欠工资" in s["matched_keywords"]


def test_alias_salary_word():
    s = extract_structured_filter("三个月没发薪水怎么办")
    assert s["active"] is True
    assert any("薪水" in m for m in s["matched_keywords"])
    assert "其他公共法规" in s["category_scope"]


def test_alias_labor_law_multi():
    s = extract_structured_filter("按劳动法怎么赔偿")
    assert s["active"] is True
    assert any("劳动法" in m for m in s["matched_keywords"])
