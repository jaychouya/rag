# 通过案例查找目录及其中的法规
import asyncio
from typing import Optional

from law_finder.jinja_env import get_template
from law_compat.text_utils import isSimilarText, split_batch_by_textlen
from law_finder.myextractor import CodeExtractor

from .llm import LLMSDK
from .utils import load_categories, load_laws_by_category


def postprocess_law_path(laws: list, final_results: list) -> list:
    for item in final_results:
        name = item["name"]
        for law in laws:
            if isSimilarText(name, law["name"], threshold=0.9):
                item["id"] = law["id"]
                item["name"] = law["name"]
                break
    
    # 处理结果，合并name相同的
    merged_results = {}
    for item in final_results:
        if not 'id' in item or item.get('index', -1) < 0:
            continue
        name = item["name"]
        if name not in merged_results:
            merged_results[name] = {"id": item["id"], "pathes": []}
        merged_results[name]["pathes"].append({"path": item["path"], "path_summary": item["path_summary"]})
    # 转成数组
    final_merged_results = []
    for name, data in merged_results.items():
        final_merged_results.append({
            "id": data["id"],
            "name": name,
            "pathes": data["pathes"],
        })
    return final_merged_results

async def parse_law_info_by_path(law_scope: str, category_scope: Optional[list[str]] = None, law_tags: Optional[list[str]] = None) -> list:
    """
    根据法律范围提取相关的法律法规目录
    :param law_scope: 法律范围
    :return: 法律法规目录
    """
    # 从数据库中查询所有法规的名字

    if not law_scope:
        return []
    categories = await load_categories(category_scope)
    categoriesids = [cat['id'] for cat in categories]
    laws = await load_laws_by_category(categoriesIds=categoriesids, law_tags=law_tags, columns=["id", "name"])

    batches = split_batch_by_textlen(laws, "name", 40, 1500)

    json_extractor = CodeExtractor(
        llm=LLMSDK,
        title="find_law_path",
    )

    # 准备所有的异步任务
    tasks = []
    for batch in batches:
        # 渲染jinja模板
        message = get_template("parse_law_path.jinja2").render({"laws": batch})
        task = json_extractor.do(message=law_scope, system_message=message)
        tasks.append(task)
    
    # 使用asyncio.gather并发执行所有任务
    try:
        results_list = await asyncio.gather(*tasks)
        final_results = []
        for results in results_list:
            final_results.extend(results)
    except Exception as e:
        print(f"解析法规范围时出错: {e}")
        raise Exception(f"解析法规范围时出错")
    # final_results格式：[{'name': '中华人民共和国民法典', 'similary': 5, 'path': [{'partname': '婚姻', 'index': None, 'unit': '编'}], 'path_summary': '婚姻编'}, {'name': '中华人民共和国人民警察法', 'similary': 5, 'path': [], 'path_summary': '整部法规'}]
    return postprocess_law_path(laws, final_results)