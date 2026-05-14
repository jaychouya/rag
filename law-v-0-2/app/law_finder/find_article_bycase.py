# 从法规中找出匹配的条目
import asyncio
import json
import logging
import os
from typing import Any, Callable, Optional

from law_compat.text_utils import isSimilarText, split_batch_by_textlen

from law_finder.jinja_env import get_template
from law_finder.myextractor import CodeExtractor
from law_finder.tree_flatten import flatten_law_children, rows_for_j1_batch

from .llm import LLMSDK
from .models import LawFindItem

logger = logging.getLogger(__name__)

def _use_legacy_tree_llm() -> bool:
    return os.getenv("LAW_FINDER_LEGACY_TREE_LLM", "").lower() in ("1", "true", "yes")


_J2_TOP = int(os.getenv("LAW_FINDER_J2_TOP", "20"))
_J2_CONTENT_PREVIEW = int(os.getenv("LAW_FINDER_J2_CONTENT_PREVIEW", "4000"))


def _content_preview(ref: dict) -> str:
    c = ref.get("content")
    if c is None:
        return ""
    if isinstance(c, (dict, list)):
        s = json.dumps(c, ensure_ascii=False)
    else:
        s = str(c)
    return s[:_J2_CONTENT_PREVIEW] if len(s) > _J2_CONTENT_PREVIEW else s


_LEGACY_MAX_DEPTH = int(os.getenv("LAW_FINDER_LEGACY_MAX_DEPTH", "4"))

async def _find_article_async_legacy(
    case: str,
    docName: str,
    lawparts: list[dict],
    json_extractor: CodeExtractor,
    extra_prompt="",
    batch_limit=20,
    scoreThreshold=3,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
    law_diag: Optional[dict[str, Any]] = None,
    _depth: int = 0,
) -> list[dict]:
    if _depth >= _LEGACY_MAX_DEPTH:
        logger.info("legacy: max depth %d reached for %s, collecting leaf nodes", _depth, docName)
        leaf_results = []
        for part in lawparts:
            if isinstance(part, dict):
                leaf_results.append(part)
        return leaf_results
    async def process_batch(batch: list[dict]) -> list[dict]:
        if not batch or len(batch) == 0:
            return []
        jinjaTpl = get_template("find_article.jinja2")

        typ = "article" if "content" in batch[0] else "section"
        message = jinjaTpl.render({"case": case, "docName": docName, "items": batch, "type": typ})

        scored_nodes = await json_extractor.do(message)
        if not scored_nodes:
            return []
        if not isinstance(scored_nodes, list):
            return []
        scored_nodes = [node for node in scored_nodes if isinstance(node, dict) and node.get("score", 0) >= scoreThreshold]
        for node in scored_nodes:
            matching_batch_item = next(
                (
                    item
                    for item in batch
                    if isSimilarText(
                        item.get("pathname", ""), node.get("name", ""), [" ", "\r", "\n", "/", "\\", "《", "》"], 0.99
                    )
                ),
                None,
            )
            if not matching_batch_item:
                logger.warning("法律条款 %s 未匹配到原始项", node.get("name"))
                continue

            for key in matching_batch_item:
                if key not in node:
                    node[key] = matching_batch_item[key]
        return scored_nodes

    if _depth == 0 and len(lawparts) > 30:
        lawparts = _prefilter_flat_nodes(lawparts, case, _NODE_PREFILTER_THRESHOLD)
        if not lawparts:
            if law_diag is not None:
                law_diag["legacy_initial_batches"] = 0
                law_diag["legacy_recursive"] = True
            return []

    batches = split_batch_by_textlen(
        lawparts, text_key_name="summary", max_batch_size=batch_limit, max_text_length=6000
    )
    unique_paths = set()
    if law_diag is not None:
        law_diag["legacy_initial_batches"] = len(batches)
        law_diag["legacy_recursive"] = True
    for law in lawparts:
        pathname = law["pathname"]
        last_slash_index = pathname.rfind("/")
        if last_slash_index != -1:
            pathname = f"{pathname[:last_slash_index].strip()}的条款"
        unique_paths.add(pathname)

    if findingMessageCallback:
        unique_paths_str = "\n ".join(unique_paths)
        findingMessageCallback(f"正在 {unique_paths_str} 中检索...")

    batch_tasks = [process_batch(batch) for batch in batches]

    try:
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    except Exception as e:
        logger.exception("processing batches: %s", e)
        if law_diag is not None:
            law_diag["mode"] = "legacy"
            law_diag["j1_ranked_pathnames"] = []
            law_diag["stage_final_pathnames"] = []
        return []

    final_results = []
    children_tasks = []

    for i, result in enumerate(batch_results):
        try:
            if isinstance(result, Exception):
                logger.error("batch %s: %s", i, result)
                continue

            useful_nodes = result
            for node in useful_nodes:
                if "children" in node and node["children"]:
                    child_task = _find_article_async_legacy(
                        case=case,
                        docName=docName,
                        lawparts=node["children"],
                        json_extractor=json_extractor,
                        extra_prompt=extra_prompt,
                        batch_limit=batch_limit,
                        scoreThreshold=scoreThreshold,
                        findingMessageCallback=findingMessageCallback,
                        law_diag=None,
                        _depth=_depth + 1,
                    )
                    children_tasks.append(child_task)
                else:
                    final_results.append(node)
        except Exception as e:
            logger.error("batch result %s: %s", i, e)
            continue

    if children_tasks:
        try:
            children_results = await asyncio.gather(*children_tasks, return_exceptions=True)
            for i, children_result in enumerate(children_results):
                if isinstance(children_result, Exception):
                    logger.error("children %s: %s", i, children_result)
                    continue
                final_results.extend(children_result)
        except Exception as e:
            logger.exception("children tasks: %s", e)
    if law_diag is not None:
        law_diag["mode"] = "legacy"
        law_diag["j1_ranked_pathnames"] = []
        law_diag["stage_final_pathnames"] = [
            n.get("pathname")
            for n in final_results
            if isinstance(n, dict) and n.get("pathname")
        ]
    return final_results


_NODE_PREFILTER_THRESHOLD = int(os.getenv("LAW_FINDER_NODE_PREFILTER_THRESHOLD", "80"))


def _prefilter_flat_nodes(flat: list[dict], case_text: str, max_nodes: int = 80) -> list[dict]:
    from law_finder.retrieval_sql import _extract_cn_keywords
    kws = _extract_cn_keywords(case_text, max_kw=12)
    if not kws:
        return flat[:max_nodes]

    def _node_score(node: dict) -> int:
        text = (node.get("summary") or "") + (node.get("pathname") or "")
        return sum(1 for kw in kws if kw in text)

    scored = [(i, _node_score(n)) for i, n in enumerate(flat)]
    min_score = 2 if len(flat) > 30 else 1
    matched = [(i, s) for i, s in scored if s >= min_score]
    if not matched and min_score > 1:
        matched = [(i, s) for i, s in scored if s > 0]
    if not matched:
        logger.info("prefilter: 0 keyword matches in %d nodes, skipping law", len(flat))
        return []
    matched.sort(key=lambda x: x[1], reverse=True)
    keep = set(i for i, _ in matched[:max_nodes])
    return [flat[i] for i in sorted(keep)]


async def _find_article_async_two_stage(
    case: str,
    docName: str,
    lawparts: list[dict],
    json_extractor: CodeExtractor,
    extra_prompt: str = "",
    batch_limit: int = 20,
    scoreThreshold: int = 3,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
    law_diag: Optional[dict[str, Any]] = None,
) -> list[dict]:
    _ = extra_prompt
    flat = flatten_law_children(lawparts)
    if law_diag is not None:
        law_diag["mode"] = "two_stage"
        law_diag["flat_count"] = len(flat)
    if not flat:
        if law_diag is not None:
            law_diag["j1_batches"] = 0
            law_diag["j2_llm_calls"] = 0
        return []

    original_count = len(flat)
    flat = _prefilter_flat_nodes(flat, case, _NODE_PREFILTER_THRESHOLD)
    if law_diag is not None:
        law_diag["prefiltered_count"] = len(flat)
    if not flat:
        logger.info("two_stage: prefilter eliminated all nodes for %s, skipping", docName)
        if law_diag is not None:
            law_diag["j1_batches"] = 0
            law_diag["j2_llm_calls"] = 0
        return []

    pathnames = {r["pathname"][: min(80, len(r["pathname"]) or 1)] for r in flat if r.get("pathname")}
    if findingMessageCallback and pathnames:
        msg = f"正在《{docName}》中检索"
        if original_count != len(flat):
            msg += f" {len(flat)}/{original_count} 个候选节点（预筛+两阶段）..."
        else:
            msg += f" {len(flat)} 个候选节点（两阶段）..."
        findingMessageCallback(msg)

    j1_rows = rows_for_j1_batch(flat)
    batches = split_batch_by_textlen(
        j1_rows, text_key_name="summary", max_batch_size=batch_limit, max_text_length=6000
    )
    if law_diag is not None:
        law_diag["j1_batches"] = len(batches)

    async def j1_batch(batch: list[dict]) -> list[dict]:
        if not batch:
            return []
        msg = get_template("find_article_j1.jinja2").render(case=case, docName=docName, items=batch)
        out = await json_extractor.do(msg)
        if not isinstance(out, list):
            return []
        good = []
        for node in out:
            if not isinstance(node, dict) or "idx" not in node:
                continue
            try:
                node["idx"] = int(node["idx"])
            except (TypeError, ValueError):
                continue
            good.append(node)
        return good

    logger.info(
        "find_article_two_stage doc=%s flat_nodes=%s j1_batches=%s",
        docName,
        len(flat),
        len(batches),
    )
    j1_parts = await asyncio.gather(*[j1_batch(b) for b in batches], return_exceptions=True)
    j1_all: list[dict] = []
    for p in j1_parts:
        if isinstance(p, Exception):
            logger.error("j1: %s", p)
            continue
        j1_all.extend(p)

    best: dict[int, dict] = {}
    for node in j1_all:
        idx = node["idx"]
        sc = int(node.get("score", 0))
        if sc < scoreThreshold:
            continue
        if idx not in best or sc > best[idx].get("score", 0):
            best[idx] = node

    ranked = sorted(best.items(), key=lambda x: x[1].get("score", 0), reverse=True)
    if law_diag is not None:
        law_diag["j1_ranked_pathnames"] = [flat[idx]["pathname"] for idx, _ in ranked if 0 <= idx < len(flat)]
    top = ranked[:_J2_TOP]
    if not top:
        if law_diag is not None:
            law_diag["stage_final_pathnames"] = []
            law_diag["j2_llm_calls"] = 0
        return []

    j2_items = []
    for idx, node in top:
        if idx < 0 or idx >= len(flat):
            continue
        ref = flat[idx]["_ref"]
        j2_items.append(
            {
                "idx": idx,
                "pathname": flat[idx]["pathname"],
                "parent_pathname": flat[idx].get("parent_pathname", ""),
                "summary": flat[idx]["summary"],
                "content_preview": _content_preview(ref) if ref.get("content") else "",
            }
        )

    if not j2_items:
        if law_diag is not None:
            law_diag["stage_final_pathnames"] = []
            law_diag["j2_llm_calls"] = 0
        return []

    if law_diag is not None:
        law_diag["j2_llm_calls"] = 1
    j2_msg = get_template("find_article_j2.jinja2").render(case=case, docName=docName, items=j2_items)
    j2_out = await json_extractor.do(j2_msg)
    final: list[dict] = []

    if isinstance(j2_out, list) and j2_out:
        for node in j2_out:
            if not isinstance(node, dict):
                continue
            try:
                idx = int(node.get("idx", -1))
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(flat):
                continue
            ref = flat[idx]["_ref"]
            if not isinstance(ref, dict):
                continue
            merged = dict(ref)
            merged["score"] = int(node.get("score", 0))
            merged["reason"] = node.get("reason", "")
            final.append(merged)
        if law_diag is not None:
            law_diag["stage_final_pathnames"] = [
                x.get("pathname") for x in final if isinstance(x, dict) and x.get("pathname")
            ]
        return final

    for idx, node in top:
        ref = flat[idx]["_ref"]
        if not isinstance(ref, dict):
            continue
        merged = dict(ref)
        merged["score"] = int(node.get("score", 0))
        merged["reason"] = node.get("reason", "J2无输出，沿用J1")
        final.append(merged)
    if law_diag is not None:
        law_diag["stage_final_pathnames"] = [x.get("pathname") for x in final if isinstance(x, dict) and x.get("pathname")]
    return final


_LEGACY_NODE_LIMIT = int(os.getenv("LAW_FINDER_LEGACY_NODE_LIMIT", "200"))

async def _find_article_async(
    case: str,
    docName: str,
    lawparts: list[dict],
    json_extractor: CodeExtractor,
    extra_prompt="",
    batch_limit=20,
    scoreThreshold=3,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
    law_diag: Optional[dict[str, Any]] = None,
    force_legacy: Optional[bool] = None,
) -> list[dict]:
    use_legacy = force_legacy if force_legacy is not None else _use_legacy_tree_llm()
    if use_legacy:
        flat_count = len(flatten_law_children(lawparts))
        if flat_count > _LEGACY_NODE_LIMIT:
            logger.info("legacy auto-downgrade to two_stage: %s has %d nodes (limit %d)", docName, flat_count, _LEGACY_NODE_LIMIT)
            use_legacy = False
    if use_legacy:
        return await _find_article_async_legacy(
            case,
            docName,
            lawparts,
            json_extractor,
            extra_prompt,
            batch_limit,
            scoreThreshold,
            findingMessageCallback,
            law_diag=law_diag,
        )
    return await _find_article_async_two_stage(
        case,
        docName,
        lawparts,
        json_extractor,
        extra_prompt,
        batch_limit,
        scoreThreshold,
        findingMessageCallback,
        law_diag=law_diag,
    )


async def find_article(
    laws: list[dict],
    case: str,
    max_llm_threads=8,
    scoreThreshold=4,
    topK=5,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
    diagnostics_out: Optional[dict[str, Any]] = None,
    force_legacy: Optional[bool] = None,
) -> list[LawFindItem]:
    is_fast = not (force_legacy is True or _use_legacy_tree_llm())
    json_extractor = CodeExtractor(
        max_workers=max_llm_threads,
        llm=LLMSDK,
        title="find_article",
        max_retry=2 if is_fast else 3,
        call_timeout=120.0 if is_fast else None,
    )

    tasks = []
    task_metadata = []
    law_diags: list[Optional[dict[str, Any]]] = []

    for law in laws:
        if "children" not in law or not law["children"]:
            continue

        ld: Optional[dict[str, Any]] = {} if diagnostics_out is not None else None
        law_diags.append(ld)
        task = _find_article_async(
            case,
            law["docName"],
            law["children"],
            json_extractor,
            batch_limit=20,
            scoreThreshold=scoreThreshold,
            findingMessageCallback=findingMessageCallback,
            law_diag=ld,
            force_legacy=force_legacy,
        )
        tasks.append(task)
        task_metadata.append(law)

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results = []

        for i, result in enumerate(results):
            try:
                if isinstance(result, Exception):
                    law = task_metadata[i]
                    logger.error("查询%s异常: %s", law.get("docName"), result)
                    continue

                law = task_metadata[i]
                law_articles = result
                law_articles.sort(key=lambda x: x["score"], reverse=True)
                ld = law_diags[i] if i < len(law_diags) else None
                if ld is not None and "stage_final_pathnames" not in ld:
                    ld["stage_final_pathnames"] = [
                        a.get("pathname") for a in law_articles if isinstance(a, dict) and a.get("pathname")
                    ]
                final_results.append({"law": law, "articles": law_articles})
            except Exception as e:
                law = task_metadata[i] if i < len(task_metadata) else {"docName": "unknown"}
                logger.error("处理%s: %s", law.get("docName"), e)
    except Exception as e:
        logger.exception("gather: %s", e)
        final_results = []

    all_articles = []
    for item in final_results:
        for article in item["articles"]:
            article["docName"] = item["law"]["docName"]
            all_articles.append(article)
    all_articles.sort(key=lambda x: x["score"], reverse=True)
    if len(all_articles) > topK:
        threshold_count = sum(1 for article in all_articles if article["score"] >= scoreThreshold)
        topK = max(threshold_count, topK)
        top_match = all_articles[:topK]
        other = all_articles[topK:]
    else:
        top_match = all_articles
        other = []
    other.sort(key=lambda x: x["docName"])

    valuable_results = []
    for v in top_match:
        valuable_results.append(
            {
                "name": v["docName"],
                "path": v.get("pathname", None),
                "content": v.get("content", None),
                "summary": v.get("summary", None),
                "scenario": v.get("scenarios_summary", None),
                "reason": v.get("reason", None),
            }
        )
    if diagnostics_out is not None:
        diagnostics_out["laws"] = []
        for i, law in enumerate(task_metadata):
            d = law_diags[i] if i < len(law_diags) else None
            if isinstance(d, dict):
                d = {**d, "docName": law.get("docName")}
            diagnostics_out["laws"].append(d or {})
        diagnostics_out["returned_paths"] = [v.get("path") for v in valuable_results]
        j1_tot = 0
        j2_tot = 0
        leg_batches = 0
        for d in diagnostics_out["laws"]:
            if not isinstance(d, dict):
                continue
            j1_tot += int(d.get("j1_batches") or 0)
            j2_tot += int(d.get("j2_llm_calls") or 0)
            leg_batches += int(d.get("legacy_initial_batches") or 0)
        diagnostics_out["find_article_parallel_laws"] = len(tasks)
        diagnostics_out["j1_batches_total"] = j1_tot
        diagnostics_out["j2_llm_calls_total"] = j2_tot
        diagnostics_out["legacy_initial_batches_total"] = leg_batches
    return valuable_results
