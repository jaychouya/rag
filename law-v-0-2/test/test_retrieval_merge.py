import os

from law_finder.retrieval_merge import merge_retrieval_doc_ids


def test_merge_union_default():
    assert sorted(merge_retrieval_doc_ids([1, 2], [2, 3], [4])) == [1, 2, 3, 4]


def test_merge_intersect(monkeypatch):
    monkeypatch.setenv("LAW_FINDER_RETRIEVAL_DOC_MERGE_MODE", "intersect")
    assert sorted(merge_retrieval_doc_ids([1, 2, 3], [2, 9], [3, 8])) == [2, 3]


def test_merge_intersect_fts_only(monkeypatch):
    monkeypatch.setenv("LAW_FINDER_RETRIEVAL_DOC_MERGE_MODE", "intersect")
    assert sorted(merge_retrieval_doc_ids([10, 20], [], [])) == [10, 20]
