# 验证分类的json和原始目录有没有出入
import json
import os

from tmindai.utils import normalize_whitespace


def validate_exist_file(json_file_path, directory_to_search):
    # 读取 JSON 文件中的文件名（不带后缀）
    with open(json_file_path, "r", encoding="utf-8") as f:
        text = f.read()
        text = normalize_whitespace(text)
        data = json.loads(text)
    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    all_laws = []

    for category_type in data:
        for cat in category_type["categories"]:
            all_laws.extend(cat["laws"])

    # 去除重复，并将名称存储为集合，以便快速查找
    laws_set = set(all_laws)

    # 用于记录不存在的文件名
    not_found_files = laws_set.copy()

    # 遍历目录及其子目录
    for root, _, files in os.walk(directory_to_search):
        for file_name in files:
            # 提取文件名去掉后缀进行比对, 后缀有两部份。 类似于，.doc.json, .docx.json等，或者 .pdf.json
            base_name_without_ext = file_name.split(".")[0].strip()
            # 标准化文件名，去除多余空格
            base_name_without_ext = normalize_whitespace(base_name_without_ext)

            if base_name_without_ext in laws_set:
                # 如果找到文件，移除它以便剩下的是未被找到的
                not_found_files.discard(base_name_without_ext)

    # 输出不存在的文件名
    if not_found_files:
        print("The following files were not found:")
        for missing_file in not_found_files:
            print(missing_file)
    else:
        print("All files are present.")


import json
import os


def reverse_check(json_file_paths, directory_to_search):
    all_laws = []
    for json_file_path in json_file_paths:
        # 读取 JSON 文件中的文件名（不带后缀）
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for category_type in data:
            for cat in category_type["categories"]:
                all_laws.extend(cat["laws"])

    # 去除重复，并将名称存储为集合以便快速查找
    laws_set = set(all_laws)
    
    # 用于记录在目录中找到但未在 JSON 中列出的文件名
    not_in_json_files = []

    # 遍历目录及其子目录
    for root, _, files in os.walk(directory_to_search):
        for file_name in files:
            # 检查文件是否为目标类型
            if file_name.lower().endswith((".doc", ".docx", ".pdf", ".json")):
                base_name_without_ext = file_name.split(".")[0].strip()
                base_name_without_ext = normalize_whitespace(base_name_without_ext)

                if base_name_without_ext not in laws_set:
                    not_in_json_files.append(os.path.join(root, file_name))

    # 输出在目录中找到但未在 JSON 中列出的文件
    if not_in_json_files:
        print("The following files are present in the directory but not listed in the JSON:")
        for missing_in_json in not_in_json_files:
            print(missing_in_json)
    else:
        print("All files in the directory are listed in the JSON.")


# 示例用法

DIST_DIR = "/Users/zhangfan/work/省厅/dsx/projects/law-agent/laws/"
LAW_DIR = os.path.join(DIST_DIR, "parsed_laws")
CATEGORY_JSON = os.path.join(DIST_DIR, "category/all_category.json")
validate_exist_file(CATEGORY_JSON, LAW_DIR)
reverse_check([CATEGORY_JSON], LAW_DIR)
