import json
import os
import re

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from law_compat.doc_pkg import read_file_content

"""
对于 macOS
使用 Homebrew 安装 libmagic：

bash
brew install libmagic
确保环境变量正确设置（通常不需要，但如果安装后仍有问题，可以尝试）：

确保 /usr/local/lib 在你的动态库路径中。
对于 Ubuntu 或其他 Debian 系统
安装 libmagic 和相关开发包：

bash
sudo apt-get update
sudo apt-get install libmagic1
sudo apt-get install libmagic-dev
重新安装 python-magic：

如果你已经安装了 python-magic，可以尝试重新安装：
bash
pip uninstall python-magic
pip install python-magic
"""


CATAGORY_LV = 1
SUBCATAGORY_LV = 2
CHAPTER_LV = 3
SECTION_LV = 4
ITEM_LV = 5
NO_LV = 1000


class SegmentMatcher:
    def __init__(self, category_match, subcategory_match, chapter_match, section_match, item_match):
        self.category_match = category_match
        self.subcategory_match = subcategory_match
        self.chapter_match = chapter_match
        self.section_match = section_match
        self.item_match = item_match


DEFAULT_MATCHER = SegmentMatcher(
    # category_match=r"第([零一二三四五六七八九十百千万]+)编\s*(\S*)",
    # subcategory_match=r"第([零一二三四五六七八九十百千万]+)分编\s*(\S*)",
    # chapter_match=r"第([零一二三四五六七八九十百千万]+)章\s*(\S*)",
    # section_match=r"第([零一二三四五六七八九十百千万]+)节\s*(\S*)",
    
    category_match=r"第([零一二三四五六七八九十百千万]+)编\s*([\s\S]+)",
    subcategory_match=r"第([零一二三四五六七八九十百千万]+)分编\s*([\s\S]+)",
    chapter_match=r"第([零一二三四五六七八九十百千万]+)章\s*([\s\S]+)",
    section_match=r"第([零一二三四五六七八九十百千万]+)节\s*([\s\S]+)",
    item_match=r"第([零一二三四五六七八九十百千万]+|[0-9]+)条\s*(.*)"
    
    
   
)


import glob
import os


def find_documents(directory, recursive=False):
    # 定义你想要搜索的文件类型
    file_types = ["*.doc", "*.docx", "*.txt", "*.md"]

    # 初始化结果列表
    files_found = []
    # 遍历每种文件类型
    for file_type in file_types:
        # 使用 glob.glob 来查找文件
        if recursive:
            pattern = os.path.join(directory, "**", file_type)
        else:
            pattern = os.path.join(directory, file_type)
        files_found.extend(glob.glob(pattern, recursive=recursive))
    return files_found

# 只支持到千
def chinese_to_arabic(chinese_num):
    try:
        # 尝试直接转换为整数
        chinese_num_int = int(chinese_num)
        if isinstance(chinese_num_int, int):
            return chinese_num_int
    except ValueError:
        pass
    chinese_digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                      '六': 6, '七': 7, '八': 8, '九': 9}
    units = {'十': 10, '百': 100, '千': 1000}
    
    # 如果只有一位数字，直接返回对应的阿拉伯数字
    if len(chinese_num) == 1:
        # 考虑十的情况
        if chinese_num in chinese_digits:
            return chinese_digits[chinese_num]
        elif chinese_num in units:
            # 如果不是有效的数字字符，返回0
            return units[chinese_num]
        else:
            raise ValueError(f"无效的字符: {chinese_num}")
    
    result = 0
    temp = 0
    i = 0

    while i < len(chinese_num):
        char = chinese_num[i]
        
        if char in chinese_digits:
            num = chinese_digits[char]
            # 检查下一个字符是否为单位，如"十", "百", "千"
            if i + 1 < len(chinese_num) and chinese_num[i + 1] in units:
                unit_char = chinese_num[i + 1]
                unit_value = units[unit_char]
                temp += num * unit_value
                i += 1
            else:
                temp += num
        elif char in units:
            # 处理以"十"，"百"，"千"开头的情况，如"十二"，"百二"
            if i == 0 or (i > 0 and chinese_num[i - 1] not in chinese_digits):
                unit_value = units[char]
                temp += unit_value
            else:
                temp *= units[char]
        else:
            raise ValueError(f"无效的字符: {char}")
        
        i += 1
    
    result += temp
    return result


import json
import re


def append_item_to_last_parent(item, parents):
    if not parents:
        # 如果parents为空，直接添加item
        parents.append(item)
        return

    # 获取最后一个父元素
    current_parent = parents[-1]

    # 比较当前父元素和新item的level
    if item["level"] > current_parent["level"]:
        # 如果item的level更高(数值更大)，添加到children中
        if "children" not in current_parent:
            current_parent["children"] = []

        # 递归处理children列表
        append_item_to_last_parent(item, current_parent["children"])
    else:
        # 如果item的level更低或相等，添加到parents同级
        parents.append(item)


def parse_regulation(text, matcher: SegmentMatcher):
    lines = text.splitlines()
    header, current_item = ("", None)
    appendHeader = True
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        category_match = re.match(matcher.category_match, line) if matcher.category_match else None
        subcategory_match = re.match(matcher.subcategory_match, line) if matcher.subcategory_match else None
        chapter_match = re.match(matcher.chapter_match, line) if matcher.chapter_match else None
        section_match = re.match(matcher.section_match, line) if matcher.section_match else None
        item_match = re.match(matcher.item_match, line) if matcher.item_match else None

        if category_match or subcategory_match or chapter_match or section_match or item_match:
            appendHeader = False

        # Match Chapters
        if category_match:
            category = {
                "index": chinese_to_arabic(category_match.group(1)),
                "categoryName": "编",
                "name": category_match.group(2),
                "level": CATAGORY_LV,
            }
            append_item_to_last_parent(category, items)

        elif subcategory_match:
            subcategory = {
                "index": chinese_to_arabic(subcategory_match.group(1)),
                "categoryName": "分编",
                "name": subcategory_match.group(2),
                "level": SUBCATAGORY_LV,
            }
            append_item_to_last_parent(subcategory, items)

        elif chapter_match:
            chapter = {
                "index": chinese_to_arabic(chapter_match.group(1)),
                "categoryName": "章",
                "name": chapter_match.group(2),
                "level": CHAPTER_LV,
            }
            append_item_to_last_parent(chapter, items)
        # Match Sections
        elif section_match:
            section = {
                "index": chinese_to_arabic(section_match.group(1)),
                "categoryName": "节",
                "name": section_match.group(2),
                "level": SECTION_LV,
            }
            append_item_to_last_parent(section, items)
        # Match Items
        elif item_match:
            # 注意处理补充条款
            item_idx = chinese_to_arabic(item_match.group(1))
            content = item_match.group(2).strip()
            if current_item and current_item["index"] == item_idx:
                # 是上一条的补充条款
                if content:
                    current_item["content"] += "\n补充条款 " + content
            else:
                current_item = {
                    "index": item_idx,
                    "content": content,
                    "level": ITEM_LV,
                }
                append_item_to_last_parent(current_item, items)
        else:
            if current_item:
                current_item["content"] += "\n" + line
            elif appendHeader:  # Before the first chapter starts
                header += f"{line}\n"

    # 提取所有的父级项里面的obj作为最终的items
    return {"docName": "", "header": header, "children": items}  # Placeholder for document name

def validateJson(json_data):
    # 找出所有的叶子节点，验证它们的“index"的最大值是否和叶子节点个数一致
    def find_leaf_nodes(node):
        if "children" not in node:
            return [node]
        leaves = []
        for child in node["children"]:
            leaves.extend(find_leaf_nodes(child))
        return leaves

    leaf_nodes = find_leaf_nodes(json_data)
    if not leaf_nodes:
        return False

    max_index = max(leaf["index"] for leaf in leaf_nodes if "index" in leaf)
    return max_index == len(leaf_nodes)

def law_to_json(file_path, output_file = None, matcher: SegmentMatcher = DEFAULT_MATCHER):
    text = read_file_content(file_path)
    regulation_data = parse_regulation(text, matcher=matcher)
    regulation_data["docName"] = file_path.rsplit(".", 1)[0].rsplit("/", 1)[-1]  # Extracting doc name from path

    if not validateJson(regulation_data):
        raise ValueError(f"Invalid JSON structure in {file_path}")
    

    # fileName = os.path.basename(file_path).rsplit(".", 1)[0]
    # jsonPath = os.path.join(cvtPath, fileName + ".json")
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(regulation_data, f, ensure_ascii=False, indent=2)
    return regulation_data