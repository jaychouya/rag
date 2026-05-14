# 精准匹配法规条目
import asyncio
import logging
from typing import Callable, Optional

from law_finder.myextractor import CodeExtractor

from .find_article_bycase import _find_article_async
from .llm import LLMSDK

logger = logging.getLogger(__name__)


async def find_article_exactly(
    laws: list[dict],
    case: str,
    max_threads=8,
    scoreThreshold=4,
    topK=5,
    findingMessageCallback: Optional[Callable[[str], None]] = None,
) -> dict:
    json_extractor = CodeExtractor(max_workers=max_threads, llm=LLMSDK, title="find_article")

    tasks = []
    task_metadata = []

    for law in laws:
        lawcontent = law["content"]
        if "children" not in lawcontent or not lawcontent["children"]:
            logger.warning("法律条款 %s 没有子条款，跳过查询。", law.get("name"))
            continue
        for key in lawcontent:
            law[key] = lawcontent[key]
        del law["content"]

        task = _find_article_async(
            case,
            law["docName"],
            law["children"],
            json_extractor,
            batch_limit=20,
            scoreThreshold=scoreThreshold,
            findingMessageCallback=findingMessageCallback,
        )
        tasks.append(task)
        task_metadata.append(law)

    final_results = []
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                law = task_metadata[i]
                logger.error("查询%s异常: %s", law.get("docName"), result)
                continue
            law = task_metadata[i]
            law_articles = result
            law_articles.sort(key=lambda x: x["score"], reverse=True)
            final_results.append({"law": law, "articles": law_articles})
    except Exception as e:
        logger.exception("find_article_exactly: %s", e)
        final_results = []

    all_articles = []
    for item in final_results:
        for article in item["articles"]:
            article["docName"] = item["law"]["docName"]
            all_articles.append(article)
    all_articles.sort(key=lambda x: x["score"], reverse=True)
    if len(all_articles) > topK:
        valuable_results = all_articles[:topK]
        other_results = all_articles[topK:]
    else:
        valuable_results = all_articles
        other_results = []
    other_results.sort(key=lambda x: x["docName"])
    return {
        "laws": valuable_results,
        "other_valuable": other_results,
    }
