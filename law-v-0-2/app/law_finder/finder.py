import asyncio
import contextvars
import json
import logging
import os
import re
from enum import Enum
from typing import Any, Callable, Optional

_mode_override: contextvars.ContextVar[str | None] = contextvars.ContextVar("law_finder_mode_override", default=None)

from law_finder.jinja_env import get_template
from law_finder.myextractor import CodeExtractor
from law_finder.perf_log import timed_stage

from .find_article_bycase import find_article
from .find_law_bycase import find_categories, find_laws
from .find_law_bypath import find_law_by_article_path, find_law_by_path, split_path_type
from .llm import LLMSDK
from .models import LawFindItem
from .parse_case import parse_case
from .parse_law_path import parse_law_info_by_path
from .petition_wiki import format_petition_wiki_for_prompt, petition_wiki_scan
from .retrieval_merge import merge_retrieval_doc_ids
from .retrieval_sql import try_search_document_ids
from .structured_filter import extract_structured_filter, structured_filter_document_ids
from .utils import load_categories, load_laws_by_category, load_laws_by_id

logger = logging.getLogger(__name__)

_RETRIEVAL_LIMIT = int(os.getenv("LAW_FINDER_RETRIEVAL_LIMIT", "80"))


def env_max_llm_threads() -> int:
    base = int(os.getenv("LAW_FINDER_MAX_LLM_THREADS", "16"))
    if _finder_mode() == "fast":
        return int(os.getenv("LAW_FINDER_FAST_MAX_LLM_THREADS", str(min(base + 4, 24))))
    return base


def _fast_skip_classify() -> bool:
    return os.getenv("LAW_FINDER_FAST_SKIP_CLASSIFY", "1").strip().lower() in ("1", "true", "yes")


def _fast_classify_heuristic(query: str) -> Optional[QuestionType]:
    q = query.strip()
    if not q:
        return None
    if re.search(r"(列出|全部法律|有哪些法|法律清单|法规列表)", q):
        return QuestionType.LAW_LIST
    if re.search(r"第[一二三四五六七八九十百千万\d]+条", q) or ("《" in q and "》" in q):
        return QuestionType.LAW_DETAIL
    return QuestionType.LAW_MATCH


def _finder_mode() -> str:
    ov = _mode_override.get()
    if ov:
        return ov
    return os.getenv("LAW_FINDER_MODE", "fast").strip().lower()


def _petition_mode_on() -> bool:
    return os.getenv("LAW_FINDER_PETITION_MODE", "0").strip().lower() in ("1", "true", "yes")


def _petition_scope_types() -> list[str]:
    raw = os.getenv("LAW_FINDER_PETITION_SCOPE", "信访")
    return [x.strip() for x in raw.split(",") if x.strip()]


class QuestionType(Enum):
    LAW_DETAIL = "law_detail"
    LAW_MATCH = "law_match"
    LAW_LIST = "law_list"


def get_summary_law_result_prompt(result: list[LawFindItem], question: str, question_type: QuestionType) -> str:
    if question_type == QuestionType.LAW_MATCH:
        jinjaTpl_path = os.path.join(os.path.dirname(__file__), "templates", "summary_prompt_query_by_case.jinja2")
    elif question_type == QuestionType.LAW_DETAIL:
        jinjaTpl_path = os.path.join(os.path.dirname(__file__), "templates", "summary_prompt_query_by_path.jinja2")
    elif question_type == QuestionType.LAW_LIST:
        jinjaTpl_path = os.path.join(os.path.dirname(__file__), "templates", "summary_prompt_query_lawlist.jinja2")
    else:
        return f"用户询问了{question}\n目前暂时无法处理用户的问题，需要告知用户。"
    tpl_name = os.path.basename(jinjaTpl_path)
    summary = get_template(tpl_name).render(law_infos=result, question=question)
    return summary


async def query_law_by_lawpath(
    query: str,
    category_scope: Optional[list[str]] = None,
    law_tags: Optional[list[str]] = None,
    max_llm_threads=8,
    progressCallback: Optional[Callable[[str], None]] = None,
) -> list[LawFindItem]:
    # 提取案件查询信息
    if not query:
        raise ValueError("用户问题描述不能为空")
    progressCallback(f"请稍等，正在查找相关的法规内容...") if progressCallback else None

    indicated_laws = None  # 指定的法规
    indicated_articles = []  # 指定的条款
    indicated_sections = []  # 指定的章节
    law_scopes = ([], [])  # 分为两类，一类是直接查询精准条款的，一类是需要使用LLM进行路径匹配的

    indicated_laws = await parse_law_info_by_path(query)
    if indicated_laws:
        # 提取path中，unit="条"的条目，并直接查询，
        laws = await load_laws_by_id([law["id"] for law in indicated_laws])
        for l1 in indicated_laws:
            for l2 in laws:
                if l1["id"] == l2["id"]:
                    l1["content"] = l2["content"]
                    break
        law_scopes = split_path_type(indicated_laws)

    if law_scopes[0]:
        (
            progressCallback(f"正在查询指定的法律条款：{', '.join([law['name'] for law in law_scopes[0]])}")
            if progressCallback
            else None
        )
        indicated_articles = find_law_by_article_path(law_scopes[0])

    if law_scopes[1]:
        (
            progressCallback(f"正在查询指定的法规信息：{', '.join([law['name'] for law in law_scopes[1]])}")
            if progressCallback
            else None
        )
        indicated_sections = await find_law_by_path(
            law_scopes[1], max_llm_workers=max_llm_threads, findingMessageCallback=progressCallback
        )
    result = []
    result.extend(indicated_articles)
    result.extend(indicated_sections)
    return result


async def query_law_by_case_info(
    query: str,
    category_scope: Optional[list[str]] = None,
    law_tags: Optional[list[str]] = None,
    max_llm_threads=8,
    progressCallback: Optional[Callable[[str], None]] = None,
) -> list[LawFindItem]:
    # 提取案件查询信息
    if not query:
        raise ValueError("案件描述不能为空")
    progressCallback(f"正在分析您描述的案件信息...") if progressCallback else None
    case_info = await parse_case(case=query, findingMessageCallback=progressCallback)
    if not case_info:
        raise ValueError("未能提取案件信息，请检查案件描述是否符合要求")

    indicated_laws = None  # 指定的法规
    indicated_articles = []
    law_scopes = ([], [])  # 分为两类，一类是直接查询精准条款的，一类是需要使用LLM进行路径匹配的

    if case_info.get("law_scope"):
        progressCallback(f"请稍等，正在为您寻找 {case_info['law_scope']} 相关信息") if progressCallback else None
        indicated_laws = await parse_law_info_by_path(case_info["law_scope"], category_scope, law_tags)
        if indicated_laws:
            # 提取path中，unit="条"的条目，并直接查询，
            laws = await load_laws_by_id([law["id"] for law in indicated_laws])
            for l1 in indicated_laws:
                for l2 in laws:
                    if l1["id"] == l2["id"]:
                        l1["content"] = l2["content"]
                        break
            law_scopes = split_path_type(indicated_laws)
    if law_scopes[0]:
        (
            progressCallback(f"正在查询指定的法律条款：{', '.join([law['name'] for law in law_scopes[0]])}")
            if progressCallback
            else None
        )
        indicated_articles = find_law_by_article_path(law_scopes[0])
        for article in indicated_articles:
            article["reason"] = "用户指定了要查询的条款, 但是并未和案例进行过匹配"
    result = None
    # 案件简述输出
    progressMessage = f"+ 案件简述：{case_info['summary']}"
    if case_info.get("relations"):
        progressMessage += f"\n+ 相关人员：{', '.join(case_info['relations'])}"
    if case_info.get("contention"):
        if len(case_info["contention"]) == 1:
            progressMessage += f"\n+ 争议焦点：{case_info['contention'][0]}"
        elif len(case_info["contention"]) > 1:
            progressMessage += "\n+ 涉及的争议焦点："
            for cont in case_info["contention"]:
                progressMessage += f"\n - {cont}"
    progressCallback(progressMessage) if progressCallback else None

    case_prompt = get_template("case_prompt.jinja2").render(case_info=case_info, law_scope=law_scopes[1])

    mode = _finder_mode()
    logger.info("law_finder mode=%s", mode)

    if mode == "original":
        result = await _case_match_original(
            case_prompt, law_scopes, category_scope, law_tags, max_llm_threads, progressCallback,
        )
    elif mode == "expert":
        result = await _case_match_enhanced(
            query, case_info, case_prompt, law_scopes, category_scope, law_tags,
            max_llm_threads, progressCallback, force_legacy=True,
        )
    else:
        result = await _case_match_enhanced(
            query, case_info, case_prompt, law_scopes, category_scope, law_tags,
            max_llm_threads, progressCallback, force_legacy=False,
        )

    result.extend(indicated_articles)
    return result


async def _case_match_original(
    case_prompt: str,
    law_scopes,
    category_scope,
    law_tags,
    max_llm_threads,
    progressCallback,
) -> list[LawFindItem]:
    laws = []
    lawids = []
    if law_scopes[1]:
        lawids = list(set([law["id"] for law in law_scopes[1]]))
    else:
        categories = await find_categories(
            case_prompt, category_scope, scoreThreshold=4, findingMessageCallback=progressCallback,
        )
        cat_ids = [c["id"] for c in categories]
        retrieval_ids = await try_search_document_ids(
            case_prompt, law_tags=law_tags, category_ids=cat_ids or None, limit=_RETRIEVAL_LIMIT,
        )
        rcount = len(retrieval_ids) if retrieval_ids else 0
        logger.info("law_finder retrieval scoped ids=%s categories=%s", rcount, len(cat_ids))
        message = f"已为您匹配以下法规类目\n"
        for category in categories:
            message += f"+ {category['name']}\n"
        message += f"\n将继续为您查找相关的法规内容，请稍后...\n"
        progressCallback(message) if progressCallback else None
        doc_filter = retrieval_ids if retrieval_ids else None
        laws = await find_laws(
            categories, max_llm_threads=max_llm_threads, case=case_prompt,
            law_tags=law_tags, scoreThreshold=4, findingMessageCallback=progressCallback,
            document_id_filter=doc_filter,
        )
        laws = laws.get("laws", [])
        lawids = list(set([law["id"] for law in laws if "id" in law]))
        if retrieval_ids:
            lawids = list({*lawids, *retrieval_ids})

    laws = await load_laws_by_id(lawids)
    messages = "为您匹配到以下的法规，请稍后，将深入为您查找相关的条款内容...\n"
    if law_scopes[1]:
        for law in law_scopes[1]:
            messages += f"+ {law['name']}\n"
    else:
        for law in laws:
            nm = law.get("name")
            if nm:
                messages += f"+ {nm}\n"
    progressCallback(messages) if progressCallback else None

    content_parts = []
    for l in laws:
        c = l.get("content")
        if not isinstance(c, dict):
            continue
        c = dict(c)
        if not c.get("docName"):
            c["docName"] = l.get("name") or ""
        content_parts.append(c)

    result = await find_article(
        content_parts, case=case_prompt, max_llm_threads=max_llm_threads,
        findingMessageCallback=progressCallback, force_legacy=True,
    )
    return result


async def _case_match_enhanced(
    query: str,
    case_info: dict,
    case_prompt: str,
    law_scopes,
    category_scope,
    law_tags,
    max_llm_threads,
    progressCallback,
    force_legacy: bool = False,
) -> list[LawFindItem]:
    kw_text = f"{query} {case_info.get('summary', '')}"
    struct_spec = extract_structured_filter(kw_text)
    merged_category_scope = None
    if category_scope or (struct_spec.get("active") and struct_spec.get("category_scope")):
        merged_category_scope = list(
            {*(category_scope or []), *(struct_spec.get("category_scope") or [])}
        )
    merged_law_tags = list({*(law_tags or []), *(struct_spec.get("tags") or [])})
    if _petition_mode_on():
        merged_category_scope = list({*(merged_category_scope or []), *_petition_scope_types()})

    wiki_task = asyncio.create_task(petition_wiki_scan(kw_text))
    wiki_hits: list = []
    wiki_ids: list[int] = []

    laws = []
    lawids = []
    run_metrics: dict[str, Any] = {}
    article_diag: dict[str, Any] = {}
    if law_scopes[1]:
        wiki_hits, wiki_ids = await wiki_task
        lawids = list(set([law["id"] for law in law_scopes[1]]))
    else:
        with timed_stage("law_match_category_law_llm"):
            ci_kws_raw = case_info.get("keywords")
            ci_kws_list: list[str] = []
            if isinstance(ci_kws_raw, list):
                ci_kws_list = [str(k) for k in ci_kws_raw if k]
            elif isinstance(ci_kws_raw, str) and ci_kws_raw.strip():
                ci_kws_list = [k.strip() for k in ci_kws_raw.split(",") if k.strip()]
            fast_direct = bool(ci_kws_list) and not force_legacy
            cat_ids: list[int] = []
            categories: list[dict] = []
            if fast_direct:
                run_metrics["find_categories_skipped"] = True
            else:
                categories = await find_categories(
                    case_prompt, merged_category_scope, scoreThreshold=4,
                    findingMessageCallback=progressCallback, metrics_out=run_metrics,
                )
                cat_ids = [c["id"] for c in categories]
            _ret_lim = _RETRIEVAL_LIMIT
            if not force_legacy:
                _ret_lim = min(_ret_lim, int(os.getenv("LAW_FINDER_FAST_RETRIEVAL_LIMIT", "45")))
            retrieval_ids = await try_search_document_ids(
                case_prompt, law_tags=merged_law_tags or None, category_ids=cat_ids or None,
                limit=_ret_lim, direct_keywords=ci_kws_list,
            )
            wiki_hits, wiki_ids = await wiki_task
            if wiki_hits and progressCallback:
                progressCallback(
                    "【信访知识库】命中："
                    + "、".join(h.get("title") or h.get("slug", "") for h in wiki_hits[:5])
                    + "\n"
                )
            fts_count = len(retrieval_ids) if retrieval_ids else 0
            if fast_direct and fts_count > 0:
                struct_ids: list[int] = []
                if wiki_ids:
                    retrieval_ids = list(dict.fromkeys([*retrieval_ids, *wiki_ids]))
                run_metrics["struct_filter_skipped"] = True
            else:
                struct_ids = await structured_filter_document_ids(struct_spec, limit=200)
                fts_ids = list(retrieval_ids) if retrieval_ids is not None else []
                merge_mode = (os.getenv("LAW_FINDER_RETRIEVAL_DOC_MERGE_MODE", "union") or "union").strip().lower()
                run_metrics["retrieval_merge_mode"] = merge_mode
                merged_list = merge_retrieval_doc_ids(fts_ids, struct_ids, wiki_ids)
                if merge_mode == "intersect":
                    retrieval_ids = merged_list
                elif merged_list:
                    retrieval_ids = merged_list
            rcount = len(retrieval_ids) if retrieval_ids else 0
            run_metrics["retrieval_id_count"] = rcount
            logger.info(
                "law_finder retrieval ids=%s cat=%s struct=%s wiki=%s fast_direct=%s",
                rcount, len(cat_ids), len(struct_ids), len(wiki_ids), fast_direct,
            )
            if categories and progressCallback:
                message = f"已为您匹配以下法规类目\n"
                for category in categories:
                    message += f"+ {category['name']}\n"
                message += f"\n将继续为您查找相关的法规内容，请稍后...\n"
                progressCallback(message)
            _FTS_SKIP_THRESHOLD = int(os.getenv("LAW_FINDER_FTS_SKIP_THRESHOLD", "24"))
            if retrieval_ids and 0 < len(retrieval_ids) <= _FTS_SKIP_THRESHOLD:
                logger.info("fast-path: FTS returned %s ids, skipping find_laws LLM", len(retrieval_ids))
                run_metrics["find_laws_skipped"] = True
                run_metrics["find_laws_candidate_count"] = len(retrieval_ids)
                lawids = list(retrieval_ids)
                progressCallback("FTS 已精准定位候选法规，跳过 LLM 评分...\n") if progressCallback else None
            else:
                doc_filter = retrieval_ids if retrieval_ids else None
                laws = await find_laws(
                    categories, max_llm_threads=max_llm_threads, case=case_prompt,
                    law_tags=merged_law_tags or None, scoreThreshold=4, findingMessageCallback=progressCallback,
                    document_id_filter=doc_filter, metrics_out=run_metrics,
                )
                laws = laws.get("laws", [])
                lawids = list(set([law["id"] for law in laws if "id" in law]))
                if not lawids and retrieval_ids:
                    lawids = list(retrieval_ids[:_FTS_SKIP_THRESHOLD])

    if wiki_ids:
        lawids = list({*lawids, *wiki_ids})

    laws = await load_laws_by_id(lawids)
    messages = "为您匹配到以下的法规，请稍后，将深入为您查找相关的条款内容...\n"
    if law_scopes[1]:
        for law in law_scopes[1]:
            messages += f"+ {law['name']}\n"
    else:
        for law in laws:
            nm = law.get("name")
            if nm:
                messages += f"+ {nm}\n"
    progressCallback(messages) if progressCallback else None

    if not force_legacy:
        _MAX_ARTICLE_LAWS = int(os.getenv("LAW_FINDER_FAST_MAX_ARTICLE_LAWS", "10"))
    else:
        _MAX_ARTICLE_LAWS = int(os.getenv("LAW_FINDER_MAX_ARTICLE_LAWS", "20"))
    if len(laws) > _MAX_ARTICLE_LAWS:
        logger.warning("Capping laws for find_article: %s -> %s", len(laws), _MAX_ARTICLE_LAWS)
        laws = laws[:_MAX_ARTICLE_LAWS]

    content_parts = []
    for l in laws:
        c = l.get("content")
        if not isinstance(c, dict):
            continue
        c = dict(c)
        if not c.get("docName"):
            c["docName"] = l.get("name") or ""
        content_parts.append(c)

    wiki_block = format_petition_wiki_for_prompt(wiki_hits)
    if wiki_block:
        case_prompt = case_prompt + "\n\n【信访知识库（离线编译摘要）】\n" + wiki_block

    with timed_stage("law_match_find_article", n_content=len(content_parts)):
        result = await find_article(
            content_parts, case=case_prompt, max_llm_threads=max_llm_threads,
            findingMessageCallback=progressCallback, diagnostics_out=article_diag,
            force_legacy=force_legacy,
        )
    run_metrics["wiki_hits"] = len(wiki_hits)
    run_metrics["wiki_doc_ids"] = len(wiki_ids)
    run_metrics["petition_mode"] = _petition_mode_on()
    for k in ("j1_batches_total", "j2_llm_calls_total", "find_article_parallel_laws", "legacy_initial_batches_total"):
        if k in article_diag:
            run_metrics[k] = article_diag[k]
    logger.info("law_match_metrics %s", json.dumps(run_metrics, ensure_ascii=False, default=str))
    if progressCallback and run_metrics:
        progressCallback(
            "[运行指标]\n" + json.dumps(run_metrics, ensure_ascii=False, indent=2, default=str)
        )
    return result


async def list_all_laws(category_scope: Optional[list[str]] = None, law_tags: Optional[list[str]] = None) -> list:
    categoriesids = []
    if category_scope:
        categories = await load_categories(category_scope=category_scope)
        categoriesids = [cat["id"] for cat in categories]
    laws = await load_laws_by_category(categoriesIds=categoriesids, law_tags=law_tags, columns=["name"])
    return laws


async def auto_query(
    query: str,
    category_scope: Optional[list[str]] = None,
    law_tags: Optional[list[str]] = None,
    max_llm_threads: Optional[int] = None,
    progressCallback: Optional[Callable[[str], None]] = None,
):
    if max_llm_threads is None:
        max_llm_threads = env_max_llm_threads()
    question_type: Optional[QuestionType] = None
    if _finder_mode() == "fast" and _fast_skip_classify():
        question_type = _fast_classify_heuristic(query)
        if question_type is not None:
            logger.info("fast-path: heuristic classify -> %s", question_type.value)
    if question_type is None:
        with timed_stage("auto_query_classify"):
            system_prompt = get_template("auto_classify.j2").render()
            code_extractor = CodeExtractor(llm=LLMSDK, max_retry=2, call_timeout=45.0)
            types_result = await code_extractor.do(message=query, system_message=system_prompt)
        question_type = QuestionType(types_result["type"])
    if progressCallback:
        progressCallback(f"[问题类型] {question_type.value}")
    query_result = None
    if question_type == QuestionType.LAW_DETAIL:
        with timed_stage("auto_query_law_detail"):
            query_result = await query_law_by_lawpath(query, category_scope, law_tags, max_llm_threads, progressCallback)
    elif question_type == QuestionType.LAW_MATCH:
        with timed_stage("auto_query_law_match"):
            query_result = await query_law_by_case_info(query, category_scope, law_tags, max_llm_threads, progressCallback)
    elif question_type == QuestionType.LAW_LIST:
        with timed_stage("auto_query_law_list"):
            query_result = await list_all_laws(category_scope, law_tags)
    else:
        return "对不起，我暂时没有能力处理您的需求  "
    if isinstance(query_result, list):
        with timed_stage("auto_query_done", n_results=len(query_result), question_type=question_type.value):
            pass
    return query_result, question_type
