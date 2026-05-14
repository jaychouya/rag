import asyncio
from typing import Callable, Optional

from law_finder.jinja_env import get_template
from law_finder.models import LawFindItem
from law_compat.text_utils import isSimilarText, normalize_whitespace
from law_finder.myextractor import CodeExtractor

from .llm import LLMSDK


def split_path_type(laws_with_path: list) -> tuple[list, list]:
    print(f"split_path_type: {len(laws_with_path)}")
    # 将laws_with_path中的pathes分为两类，一类是直接查询精准条款的，一类是需要使用LLM进行路径匹配的
    exactly_path = []
    other_path = []
    for law in laws_with_path:
        if "pathes" in law and law["pathes"]:
            for path_item in law["pathes"]:
                item = {
                    "name": law["name"],
                    "id": law["id"],
                    "law": law["content"],
                    "path_summary": path_item["path_summary"],
                    "path": path_item["path"],
                }
                if path_item.get("path", None) is None and not path_item.get("path_summary", None):
                    print(f"[Warning] Law Path {path_item['path_summary']} does not have a path, skipping.")
                    continue
                print(f"path_item: {path_item}")
                last_item = path_item["path"][-1] if path_item["path"] else None
                if last_item and last_item["index"] and last_item["unit"] == "条":
                    exactly_path.append(item)
                else:
                    other_path.append(item)
    return exactly_path, other_path


def find_law_by_article_path(laws_with_path: list):
    # 根据条目编号查询
    """
    递归遍历law的children及其子节点，直到叶子节点（没有children但是有contennt)，如果叶子节点的index 等于article_number，则返回该叶子节点
    """
    find_result = []

    def find_article_in_children(children, article_number) -> Optional[dict]:
        for child in children:
            if "children" in child and child["children"]:
                result = find_article_in_children(child["children"], article_number)
                if result:
                    return result
            if "index" in child and str(child["index"]) == str(article_number):
                return child
        return None

    for law in laws_with_path:
        if not law.get("path", None):
            print(f"[Warning] Law Path {law['path_summary']}  does not have a path, skipping.")
            continue
        if law["path"][-1]["unit"] != "条":
            print(f"[Warning] Law Path {law['path_summary']} does not end with '条', skipping.")
            continue
        try:
            article_number = int(law["path"][-1]["index"])
        except Exception:
            print(f"[Warning] Law Path {law['path_summary']} does not have a valid article number, skipping.")
            continue
        if not law.get("law", None) or not law["law"].get("children", None):
            print(f"[Warning] Law {law['name']} does not have content, skipping.")
            continue
        article_node = find_article_in_children(law["law"]["children"], article_number)
        find_result.append(
            {
                "path": article_node.get("pathname") if article_node else law.get("path_summary", None),
                "name": law["name"],
                "content": article_node.get("content", None) if article_node else None,
                "summary": article_node.get("summary", None) if article_node else None,
                "scenario": article_node.get("scenarios_summary", None) if article_node else None,
            }
        )
    return find_result


async def find_law_by_path(laws_with_path: list, max_llm_workers=8, findingMessageCallback: Optional[Callable[[str], None]] = None) -> list[LawFindItem]:
    find_result = []

    # 接下来针对每本法规所有children的pathname，使用LLM判定是否和剩下的law_with_path中的pathes有重合
    async def match_path_with_llm(json_extractor: CodeExtractor, lawName: str, nodes: list, pathname: str):
        try:
            pathname = normalize_whitespace(pathname)  # 规范化路径名
            pathes = [normalize_whitespace(n["pathname"]) for n in nodes]
            message = get_template("find_law_path.jinja2").render(
                {"docName": lawName, "pathes": pathes, "path_name_compare": pathname}
            )
            # 调用LLM服务进行匹配
            result = await json_extractor.do(message)
            if result and isinstance(result, dict) and result.get("path_name", None):
                for node in nodes:
                    if isSimilarText(
                        node.get("pathname", ""),
                        result["path_name"],
                        str2remove=["/", "《", "》", "\\", "（", "）", "-", "—", "_", "——"],
                    ):
                        return {"node": node, "finish": result.get("finish", False) if isinstance(result, dict) else False}
            return {"node": None, "finish": True}
        except Exception as e:
            print(f"Error in match_path_with_llm: {e}")
            return {"node": None, "finish": True}

    async def recursive_match_pathname(
        json_extractor: CodeExtractor,
        law_name: str,
        nodes: list,
        pathname: str,
    ):
        """
        递归匹配路径名，直到找到叶子节点
        """
        if not nodes:
            return None
        matched_node = await match_path_with_llm(json_extractor, law_name, nodes, pathname)
        node = matched_node.get("node", None)
        finish = matched_node.get("finish", False)
        if finish:
            return node
        if not node:
            return None
        if not "children" in node:  # 如果已经是叶子节点，但是又没结束，说明已经无法找到
            return None

        # 递归调用异步版本
        try:
            result = await recursive_match_pathname(json_extractor, law_name, node["children"], pathname)
        except Exception as e:
            print(f"Error in recursive_match_pathname: {e}")
            result = None

        return result

    json_extractor = CodeExtractor(
        max_workers=max_llm_workers,
        llm=LLMSDK,
        title="find_law",
    )
    
    # 准备异步任务
    tasks = []
    task_metadata = []
    
    for p in laws_with_path:
        path_name = p["path_summary"]
        if path_name == "整部法规":
            law_content = p.get("law", None)
            find_result.append(
                {
                    "id": p.get("id", None),
                    "name": p.get("name", None),
                    "path_summary": law_content.get("pathname") if law_content else p["path_summary"],
                    "node": {
                        "summary": law_content.get("summary", None) if law_content else None,
                        "scenarios_summary": law_content.get("scenarios_summary", None) if law_content else None,
                    },
                }
            )
            continue
        
        law = p["law"]
        task = recursive_match_pathname(json_extractor, law["docName"], law["children"], path_name)
        tasks.append(task)
        task_metadata.append(p)
    
    # 使用asyncio.gather并发执行所有任务
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            try:
                if isinstance(result, Exception):
                    print(f"Error processing task {i}: {result}")
                    continue
                
                path_item = task_metadata[i]
                find_result.append(
                    {
                        "id": path_item["id"],
                        "name": path_item["name"],
                        "path_summary": path_item["path_summary"],
                        "node": result,
                    }
                )
            except Exception as e:
                print(f"Error processing result {i}: {e}")
    except Exception as e:
        print(f"Error in asyncio.gather: {e}")
    final_result = []
    for article in find_result:
        node = article.get("node", None)
        final_result.append(
            {
                "name": article.get("name", None),
                "path": node.get("pathname") if node else article.get("path_summary", None),
                "content": node.get("content") if node else None,
                "summary": node.get("summary") if node else None,
                "scenario": node.get("scenarios_summary", None) if node else None,
            }
        )
    return final_result
