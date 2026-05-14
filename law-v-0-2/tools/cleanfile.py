# 读取json文件，递归删除所有children中的’pathname', 'summary', indexwords, explains, scenarios scenarios_summary 这些字段
import json
import os

"""
清除已经解析好的内容
"""
def remove_specified_fields(data):
    """
    递归删除指定的字段：'pathname', 'summary', 'indexwords', 'explains', 'scenarios', 'scenarios_summary'
    """
    fields_to_remove = {'pathname', 'summary', 'indexwords', 'explains', 'scenarios', 'scenarios_summary'}
    
    if isinstance(data, dict):
        for key in list(data.keys()):
            if key in fields_to_remove:
                del data[key]

        # Recursively process all children if they exist
        if 'children' in data:
            for child in data['children']:
                remove_specified_fields(child)

    elif isinstance(data, list):
        for item in data:
            remove_specified_fields(item)

    return data

def load_and_clean_json(file_path):
    """
    从文件加载 JSON 数据，递归删除指定字段，并返回清理后的数据。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cleaned_data = remove_specified_fields(data)
    return cleaned_data


def clean_dir(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cleaned_data = remove_specified_fields(data)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=4)


clean_dir('test')
