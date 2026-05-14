import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from law_compat.code_extractor import CodeExtractor
from law_compat.openai_sdk import OpenAICompatibleSDK
from law_compat.text_utils import split_batch_by_textlen
from tqdm import tqdm

# 使用豆包做summary
LLM_BASE_URL = os.getenv('SUMMARY_LLM_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3/")
LLM_API_KEY = os.getenv('SUMMARY_LLM_API_KEY', "49804449-6de9-40be-9fb1-37a838884bb0")
LLM_MODEL = os.getenv('SUMMARY_LLM_MODEL', "doubao-1-5-pro-256k-250115")

SUMMARY_SEPERATOR = "\n\n\n"


ignore_count = 0


def load_law_json(file_path: str) -> dict:
    """
    Load a JSON file containing law data.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        dict: The parsed JSON data.
    """
    total_child = 0

    def generate_pathname(node, parent_pathname=""):
        nonlocal total_child
        """
        递归地为JSON节点生成pathname。
        """
        # 如果当前节点是根节点，设置它的pathname为docName。
        if "docName" in node:
            node["pathname"] = node["docName"]

        # 非根节点的处理
        else:
            index = node.get("index", "")
            categoryName = node.get("categoryName", "")
            name = node.get("name", "")

            # 判断是否为叶子节点
            is_leaf = "children" not in node or not node["children"]

            # 根据是否为叶子节点生成相应的pathname
            if is_leaf:
                node["pathname"] = f"{parent_pathname}/第{index}条"
            else:
                name_part = f" {name}" if name else ""
                node["pathname"] = f"{parent_pathname}/第{index}{categoryName}{name_part}"
            total_child += 1

        # 递归处理子节点
        if "children" in node:
            for child in node["children"]:
                generate_pathname(child, node["pathname"])

        return node

    def validate_json_structure(data: dict) -> None:
        """递归验证每个节点及其chil都有path，pathname和sibling_path"""
        if not isinstance(data, dict):
            raise ValueError("JSON data must be a dictionary.")
        if "children" not in data and "content" not in data:
            raise ValueError("JSON data must contain either 'children' or 'content' key.")
        for item in data["children"]:
            if "pathname" not in item:
                raise ValueError("Each child must have 'path', 'pathname' keys.")
            if "children" in item:
                validate_json_structure(item)

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    data = generate_pathname(data)
    validate_json_structure(data)
    return data, total_child


def get_node_by_path(json_data: dict, path: list) -> dict:
    """
    Get a node from the JSON data by its path.

    Args:
        json_data (dict): The JSON data.
        path (list): The path to the node.

    Returns:
        dict: The node if found, otherwise None.
    """
    current_node = json_data
    for index in path:
        found = False
        for child in current_node.get("children", []):
            if child["index"] == index:
                current_node = child
                found = True
                break
        if not found:
            raise ValueError(f"Node with index {index} not found in path {path}.")
    return current_node


class SummaryService:
    class SummaryMethod(Enum):
        PART_REDUCE = "PART_REDUCE"
        ALL_REDUCE = "ALL_REDUCE"

    def __init__(
        self,
        llm,
        max_workers=5,
        max_retry=3,
        sentense_seperator="\n\n\n",
        summary_method: SummaryMethod = SummaryMethod.PART_REDUCE,
        title="summary_service",
    ) -> None:
        self.summary_service = CodeExtractor(
            max_workers=max_workers,
            llm=llm,
            max_retry=max_retry,
            title=title,
        )
        self.sentense_seperator = sentense_seperator
        self.summary_method = summary_method
        self.executor = ThreadPoolExecutor(thread_name_prefix="summary_reducer", max_workers=4)

    def _format_text(self, node: dict) -> str:
        sinario = node.get("scenarios_summary", "")
        sinario = f"\n+ 适用场景：{sinario}" if sinario else ""
        summary = node.get("summary", "")
        summary = f"\n+ 概述：{summary}" if summary else ""
        content = ""
        if not summary:
            content = node.get("content", "")
            if not content:
                raise ValueError(f"Node {node.get('pathname', '')} has no summary or content.")
            content = f"\n+ 内容：{content}"
        combined_text = f"# {node.get('pathname', '')}{content}{summary}{sinario}"
        return combined_text
    def validation_method(self, data: dict) -> bool:
        """
        验证 JSON 数据的结构是否符合要求。
        1. 确保每个叶子节点都包含 'scenarios_summary' 和 'scenarios' 字段。
        2. 确保非叶子节点不包含 'content' 字段。
        """
        if not isinstance(data, dict):
            return False
        if "scenarios_summary" not in data or not data["scenarios_summary"]:
            return False
        if 'summary' not in data or not data['summary']:
            return False
        return True
    
    def summary(self, nodes: list, prompt: str, max_text_length=8000) -> dict | list:
        if len(nodes) == 0:
            print('[WARNING] receive empty nodes, return empty dict')
            return {}
        if len(nodes) == 1:
            return self.summary_service.do(f"{prompt}\n\n{self._format_text(nodes[0])}", validation_method=self.validation_method)
        
        summary_method = (
            self._summary_with_agent_byparts
            if self.summary_method.value == "PART_REDUCE"
            else self._summary_with_agent_allreduce
        )
        return summary_method(nodes=nodes, prompt=prompt, max_text_length=max_text_length)
        
        

    # 假设这是一个耗时的总结函数，返回一个对象
    def _summary_with_agent_byparts(self, nodes, prompt, max_text_length) -> dict:
        def merge_batches(batches):
            merged = []
            temp = []

            for batch in batches:
                # 检查是否为单个元素的数组
                if len(batch) == 1:
                    temp.append(batch[0])  # 将这个单个元素添加到临时列表中
                    # 如果临时列表中的元素数量达到了2，则合并并清空临时列表
                    if len(temp) == 2:
                        merged.append(temp)
                        temp = []
                else:
                    # 如果当前批次不是单元素或临时列表非空，则先处理临时列表
                    if temp:
                        merged.append(temp)
                        temp = []
                    # 直接将当前批次添加到合并结果中
                    merged.append(batch)
            
            # 处理剩余的临时列表中的元素（如果有）
            if temp:
                merged.append(temp)

            return merged

        # 示例用法
        if len(nodes) == 0:
            print('[WARNING] receive empty nodes, return empty dict')
            return {}
        batches = split_batch_by_textlen(nodes, text_key_name=["pathname", "summary","scenarios_summary"] , max_text_length=max_text_length - len(prompt), max_batch_size=None)
        batches = merge_batches(batches)  # 合并批次，保证每个batch的元素个数至少为2
        # 保证每个batch的元素个数至少为2
        
        if len(batches) == 1:
            combined_text = ""
            for node in batches[0]:
                combined_text += self._format_text(node) + "\n-----\n"
            result = self.summary_service.do(f"{prompt}\n\n{combined_text}", validation_method=self.validation_method)
            if not isinstance(result, dict):
                raise ValueError(f"Summary service returned non-dict result: {result}")
            return result
        
        # 如果文本长度超出限制，则进行分段处理
        futures = {}
        for index, batch in enumerate(batches):
            combined_text = ""
            for node in batch:
                combined_text += self._format_text(node) + "\n-----\n"
            future =self.executor.submit(self.summary_service.do, f"{prompt}\n\n{combined_text}", self.validation_method)
            futures[future] = index
            time.sleep(0.05)
        results = [None] * len(futures.keys())
        for future in as_completed(futures):
            try:
                index = futures[future]
                results[index] = future.result()
            except Exception as e:
                print(f"Error summarizing batch: {e}")
                raise e
        return self._summary_with_agent_byparts(results, prompt=prompt, max_text_length=max_text_length)
    
    def _summary_with_agent_allreduce(self, nodes, prompt, max_text_length) -> dict:
        node_index = 0
        nodes_to_summary = [nodes[0]]
        while node_index < len(nodes):
            node = nodes[node_index]
            current_text = self._format_text(node)
            next_node_index = node_index + 1
            current_text_len = len(current_text)
            while next_node_index < len(nodes):
                next_node = nodes[next_node_index]
                next_text = self._format_text(next_node)
                if len(nodes_to_summary) == 1 or current_text_len + len(next_text) <= (max_text_length - len(prompt)):
                    # 如果只有一个节点，则直接拼接
                    current_text += next_text
                    nodes_to_summary.append(next_node)
                    current_text_len += len(next_text)
                    next_node_index += 1
                else:
                    # 如果拼接后超过限制，则停止拼接
                    break
            combined_text = "\n".join(self._format_text(n) for n in nodes_to_summary)
            node = self.summary_service.do(f"{prompt}\n\n{combined_text}")
            nodes_to_summary=[node]
            node_index = next_node_index
            
        return nodes_to_summary[0]

    def _process_queue(self) -> None:
        """从队列中取出任务并执行"""
        while not self.task_queue.empty():
            task = self.task_queue.get()
            try:
                task()
            except Exception as e:
                print(f"Error executing task: {e}")
            finally:
                self.task_queue.task_done()


def get_prompt_by_node(law_json: dict, node: dict) -> str:
    """
    根据节点信息生成提示语。不同类型的节点，需求不同，字数要求也不同
    1. 根据兄弟节点的个数，字数可能要求少一点，尽量让所有兄弟节点都可以在后期一次性加入打分阶段
    2. 叶子节点，不限制总结字数。适用场景要丰富。
    """
    from jinja2 import Environment, FileSystemLoader

    jinja_file = os.path.join(os.path.dirname(__file__), "summary_prompt.jinja2")
    node_type = "section"
    if "content" in node:
        node_type = "item"
    elif "docName" in node:
        node_type = "doc"
    env = Environment(loader=FileSystemLoader(os.path.dirname(jinja_file)))
    template = env.get_template(os.path.basename(jinja_file))
    max_summary_len = None
    min_summary_len = 250
    path_name = node["pathname"] if "pathname" in node else node.get("docName", "法律法规文档")
    if not "content" in node:
        if "path" in node:
            parent_path = node["path"][:-1]
            parent = get_node_by_path(law_json, parent_path)
            sibling_count = len(parent.get("children", []))
            MAX_TEXT_LEN = 8000
            MAX_SUMMARY_LEN = 1000
            MIN_SUMMARY_LEN = 250
            max_summary_len = max(min(MAX_TEXT_LEN // sibling_count, MAX_SUMMARY_LEN), MIN_SUMMARY_LEN)
            # Qwen-72B-128K的实际字数和指定的字数基本上为 1:1，所以这里直接使用mmax_summary_len
            # Doubao-pro-128K的实际字数和指定的字数基本上为 1:2，所以这里直接使用max_summary_len * 2
            max_summary_len = max_summary_len * 2
            min_summary_len = MIN_SUMMARY_LEN * 2
            
        else:
            # 如果没有path，说明是文档级别的节点
            max_summary_len = 1500

    return template.render(type=node_type, path_name=path_name, max_summary_len=max_summary_len, min_summary_len=min_summary_len)


def process_node(
    law_json: dict,
    node: dict,
    executor: ThreadPoolExecutor,
    summary_service: SummaryService,
    batch_count=5,
    ignore_level=1000,
    pbar: tqdm = None,
) -> dict:
    global ignore_count
    if "content" in node:
        # 如果是叶子节点，直接总结其内容
        if not node.get('summary', None) or ("level" in node and node["level"] < ignore_level):
            node["summary"] = ""
            ret = summary_service.summary(
                nodes=[node],
                prompt=get_prompt_by_node(law_json, node),
            )
            for key in ret:
                node[key] = ret[key]
            # 如果已经有summary了，并且level大于ignore_level，则不再进行总结
        else:
            ignore_count += 1
        if pbar:
            pbar.update(1)
        return node
    else:
        # 如果不是叶子节点，异步总结所有子节点
        # 分批次处理，每次处理5个child
        results = [None] *len(node.get("children", []))
        for i in range(0, len(node["children"]), batch_count):
            futures = {}
            chunk = node["children"][i : i + batch_count]
            for cIdx, child in enumerate(chunk):
                future = executor.submit(
                        process_node,
                        law_json=law_json,
                        node=child,
                        executor=executor,
                        summary_service=summary_service,
                        batch_count=batch_count,
                        ignore_level=ignore_level,
                        pbar=pbar)
                futures[future] = i + cIdx
                time.sleep(0.1)
            # 等待所有子节点处理完成
            for future in as_completed(futures):
                try:
                    index = futures[future]
                    results[index] = future.result()
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error processing child node:{child.get('pathname', '')}\n{e}")
        
        if len(results) != len(node["children"]):
            print(
                f"[Error]{node.get('pathname', '')} processed {len(results)} children, but expected {len(node['children'])} children."
            )
        if not node.get('summary', None) or ("level" in node and node["level"] < ignore_level):
            node["summary"] = ""
            prompt = get_prompt_by_node(law_json, node)
            ret = summary_service.summary(results, prompt)
            for key in ret:
                node[key] = ret[key]
        else:
            ignore_count += 1
        if pbar:
            pbar.update(1)
        return node


def summary_law_json(file_path, max_llm_threads=3, batch_count=3, ignore_level=1000) -> dict:
    """
    Summarize the law JSON file and save the results back to the file.
    Args:
        file_path (str): The path to the law JSON file.
        max_summary_threads (int): Maximum number of threads for summarization.
        batch_count (int): Number of child nodes to process in each batch. 太大的batchcount，如果法规层级很多，会导致线程开太多
        ignore_level: 节点中只要level大于这个level，如果已经有summary，就无需再进行总结
    """
    json_data, total_child = load_law_json(file_path)
    pbar = tqdm(total=total_child + 1, desc="待总结的节点", unit="node")

    summary_service = SummaryService(
        max_workers=max_llm_threads,
        llm=OpenAICompatibleSDK(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL),
        max_retry=10,
        sentense_seperator=SUMMARY_SEPERATOR,
        title=os.path.basename(file_path),
    )

    with ThreadPoolExecutor(thread_name_prefix="process_node", max_workers=300) as executor:
        # 对所有child改成分批次处理，每次最多处理5个child
        for i in range(0, len(json_data["children"]), batch_count):
            chunk = json_data["children"][i : i + batch_count]
            futures = []
            for child in chunk:
                future = executor.submit(
                    process_node,
                    law_json=json_data,
                    node=child,
                    executor=executor,
                    summary_service=summary_service,
                    batch_count=batch_count,
                    ignore_level=ignore_level,
                    pbar=pbar,
                )
                time.sleep(0.1)
                futures.append(future)
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing node: {child.get('pathname', '')}\n{e}")
    # 最终对整份文档一级节点进行总结
    prompt = get_prompt_by_node(json_data, json_data)
    try:
        final_summary = summary_service.summary(nodes=json_data["children"], prompt=prompt, max_text_length=8000)
        for key in final_summary:
            json_data[key] = final_summary[key]
        pbar.update(1)
    except Exception as e:
        print(f"Error summarizing final document: {e}")
    finally:
        pbar.close()

    print(f"忽略了 {ignore_count} 个节点")
    # 验证每个节点都有summary, 如果没有的话，把pathname记录，并最后打印
    error_nodes = []
    valid_count = 0


    def validate_summary(data):
        """
        检查 JSON 数据中的叶子节点，确保它们包含 'scenarios_summary' 和 'scenarios' 字段。
        """
        nonlocal valid_count, error_nodes
        if isinstance(data, dict):
            valid_count += 1
            if 'summary' not in data or not data['summary']:
                    raise ValueError(f"节点 {data['pathname']}缺失字段: summary")
            if 'scenarios_summary' not in data:
                    raise ValueError(f"节点 {data['pathname']}缺失字段: scenarios_summary")
                
            if 'children' not in data:  # Check if it's a leaf node
                if 'scenarios' not in data:
                    raise ValueError(f"节点 {data['pathname']}缺失字段: scenarios")
                if 'content' not in data or not data['content']:
                    raise ValueError(f"节点 {data['pathname']}缺失字段: content")
                return True
            else:
                # 非叶子节点不能有content
                if 'content' in data:
                    raise ValueError(f"节点 {data['pathname']}不应包含字段: content")
            # Recursively check all children if they exist
            if 'children' in data:
                for child in data['children']:
                    return validate_summary(child)

    try:
        validate_summary(json_data)
    except ValueError as e:
        print(f"验证失败: {e}")
        error_nodes.append(e)
    print(f"总共验证了 {valid_count} 个节点")
    if error_nodes:
        print(f"以下节点存在问题: {error_nodes}")
    else:
        print("所有节点都正常")
    return json_data
