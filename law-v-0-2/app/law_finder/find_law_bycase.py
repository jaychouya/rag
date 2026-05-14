# 通过案例查找目录及其中的法规
import asyncio
import logging
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

    batches = split_batch_by_textlen(laws, text_key_name="summary", max_batch_size=10, max_text_length=4000)
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
    
    # 使用asyncio.gather并发执行所有任务
    try:
        results_list = await asyncio.gather(*tasks)
        final_results = []
        for results in results_list:
            final_results.extend(results)
    except Exception as e:
        raise e
        
    final_results = [res for res in final_results if res["score"] >= scoreThreshold]
    # 根据名字去原数组中查找id
    for res in final_results:
        found = False
        for law in laws:
            if res["name"] == law["name"]:
                res["id"] = law["id"]
                res["summary"] = law["summary"]
                res["scenarios"] = law["scenarios"]
                found = True
                break
        if not found:
            print(f"Warning: Law {res['name']} not found in original laws, skipping.")
            final_results.remove(res)
    
    
    # 查询law的详细信息
    laws = await load_laws_by_id([law['id'] for law in final_results])
   
    # 检查是不是有content没有的law
    for law in laws:
        if not law.get("content"):
            print(f"[Warning] 《{law['name']}》法律条款内容缺失，跳过查询")
            final_results = [res for res in final_results if res["id"] != law["id"]]
    # 将查询到的法律条款content添加到结果中
    for res in final_results:
        found = False
        for law in laws:
            if res["id"] == law["id"]:
                found = True
                res["content"] = law["content"]
                if res['name'] != law['name']:
                    final_results.remove(res)
                    print(f"[Warning] 解析出错：《{res['name']}》法律条款名称与《{law['name']}》不一致")
                break
        if not found:
            print(f"[Warning] 《{res['name']}》法律条款和原库不匹配，跳过查询")
            final_results.remove(res)

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
    
    # 使用asyncio.gather并发执行所有任务
    try:
        results_list = await asyncio.gather(*tasks)
        final_results = []
        for results in results_list:
            final_results.extend(results)
    except Exception as e:
        raise e
        
    final_results = [res for res in final_results if res["score"] >= scoreThreshold]
    # 根据名字去原数组中查找id
    for res in final_results:
        found = False
        for category in categories:
            if res["name"] == category["name"]:
                res["id"] = category["id"]
                res["type"] = category["type"]
                res["summary"] = category["summary"]
                found = True
                break
        if not found:
            print(f"Warning: Category {res['name']} not found in original categories, skipping.")
            final_results.remove(res)
    final_results = sorted(final_results, key=lambda x: x["score"], reverse=True)[:topK]
    return final_results
