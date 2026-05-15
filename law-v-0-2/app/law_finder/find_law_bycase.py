# 通过案例查找目录及其中的法规
import asyncio
import logging
import os
from typing import Any, Callable, Optional

from law_finder.jinja_env import get_template
from law_compat.text_utils import split_batch_by_textlen
from law_finder.myextractor import CodeExtractor

from .llm import LLMSDK
from .utils import load_categories, load_laws_by_category, load_laws_by_id

logger = logging.getLogger(__name__)


async def find_laws(
    categories,
    case: str,
    law_tags: Optional[list[str]] = None,
    max_llm_threads=8,
    scoreThreshold=4,
    topK=5,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
    document_id_filter: Optional[list[int]] = None,
    metrics_out: Optional[dict[str, Any]] = None,
) -> dict:
    laws = await load_laws_by_category(
        categoriesIds=[cat["id"] for cat in categories],
        law_tags=law_tags,
        columns=["id", "name", "summary", "scenarios"],
        document_id_filter=document_id_filter,
    )
    logger.info("find_laws candidate_count=%s filter=%s", len(laws), len(document_id_filter or []))
    findingMessageCallback("正在查询可以参考的法规，请稍等...\n") if findingMessageCallback else None

    fl_batch = int(os.getenv("LAW_FINDER_FIND_LAWS_BATCH", "14"))
    batches = split_batch_by_textlen(
        laws, text_key_name="summary", max_batch_size=max(6, min(fl_batch, 20)), max_text_length=4000
    )
    if metrics_out is not None:
        metrics_out["find_laws_candidate_count"] = len(laws)
        metrics_out["find_laws_batches"] = len(batches)
        metrics_out["find_laws_llm_calls"] = len(batches)

    json_extractor = CodeExtractor(
        max_workers=max_llm_threads, llm=LLMSDK, title="find_law",
        max_retry=1, call_timeout=60.0,
    )
    
    # 准备异步任务
    tasks = []
    for batch in batches:
        message = get_template("find_laws.jinja2").render({"case": case, "laws": batch})
        task = json_extractor.do(message=message)
        tasks.append(task)
    
    try:
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        final_results = []
        for r in results_list:
            if isinstance(r, Exception):
                logger.error("find_laws batch: %s", r)
                continue
            if isinstance(r, list):
                final_results.extend(r)
    except Exception as e:
        raise e

    final_results = [res for res in final_results if isinstance(res, dict) and res.get("score", 0) >= scoreThreshold]
    matched = []
    for res in final_results:
        for law in laws:
            if res.get("name") == law["name"]:
                res["id"] = law["id"]
                res["summary"] = law["summary"]
                res["scenarios"] = law["scenarios"]
                matched.append(res)
                break
        else:
            logger.warning("Law %s not found in original laws, skipping.", res.get("name"))
    final_results = matched

    laws = await load_laws_by_id([law['id'] for law in final_results])
   
    content_by_id = {}
    for law in laws:
        if law.get("content"):
            content_by_id[law["id"]] = law
        else:
            logger.warning("《%s》法律条款内容缺失，跳过", law.get("name"))

    kept = []
    for res in final_results:
        rid = res.get("id")
        if rid not in content_by_id:
            logger.warning("《%s》法律条款和原库不匹配，跳过", res.get("name"))
            continue
        law = content_by_id[rid]
        if res.get("name") != law.get("name"):
            logger.warning("解析出错：《%s》名称与《%s》不一致", res.get("name"), law.get("name"))
            continue
        res["content"] = law["content"]
        kept.append(res)
    final_results = kept

    final_results = sorted(final_results, key=lambda x: x["score"], reverse=True)
    valuable_results = final_results[:topK]
    other_results = final_results[topK:] if len(final_results) > topK else []
    final_results = {
        "laws": valuable_results,
        "other_valuable": other_results,
    }
    
    return final_results


async def find_categories(case, category_scope: Optional[list[str]] = None, scoreThreshold=4, topK=5, findingMessageCallback: Optional[Callable[[str], None]] = None, metrics_out: Optional[dict[str, Any]] = None) -> list[dict]:
    categories = await load_categories(category_scope)
    findingMessageCallback('正在根据案件事实定位法规范围') if findingMessageCallback else None
    batches = split_batch_by_textlen(categories, text_key_name="summary", max_batch_size=10, max_text_length=4000)
    if metrics_out is not None:
        metrics_out["find_categories_batches"] = len(batches)
        metrics_out["find_categories_llm_calls"] = len(batches)
        metrics_out["find_categories_pool"] = len(categories)

    json_extractor = CodeExtractor(
        max_workers=len(batches), llm=LLMSDK, title="find_category",
        max_retry=1, call_timeout=60.0,
    )
    
    # 准备异步任务
    tasks = []
    for batch in batches:
        message = get_template("find_category.jinja2").render({"case": case, "categories": batch})
        task = json_extractor.do(message=message)
        tasks.append(task)
    
    try:
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        final_results = []
        for r in results_list:
            if isinstance(r, Exception):
                logger.error("find_categories batch: %s", r)
                continue
            if isinstance(r, list):
                final_results.extend(r)
    except Exception as e:
        raise e

    final_results = [res for res in final_results if isinstance(res, dict) and res.get("score", 0) >= scoreThreshold]
    matched = []
    for res in final_results:
        for category in categories:
            if res.get("name") == category["name"]:
                res["id"] = category["id"]
                res["type"] = category["type"]
                res["summary"] = category["summary"]
                matched.append(res)
                break
        else:
            logger.warning("Category %s not found, skipping.", res.get("name"))
    final_results = sorted(matched, key=lambda x: x.get("score", 0), reverse=True)[:topK]
    return final_results
