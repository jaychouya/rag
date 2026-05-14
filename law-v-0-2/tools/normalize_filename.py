import json
import os
import re

from tmindai.utils import normalize_whitespace


def remove_digit_prefix(name):
    """移除文件名前面的数字和连接符号的前缀。"""
    pattern = re.compile(r'^[\d\-.、]+')
    return re.sub(pattern, '', name)

def process_directory(directory):
    modified_files = []
    modified_jsons = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.doc', '.docx', '.pdf','.json')):
                file_path = os.path.join(root, file)
                normalize_filename = normalize_whitespace(remove_digit_prefix(file))
                if normalize_filename != file:
                    modified_files.append((file_path, normalize_filename))
                    # rename the file
                    new_file_name = normalize_filename
                    new_file_path = os.path.join(root, new_file_name)
                    os.rename(file_path, new_file_path)
                    if new_file_name.endswith('.json'):
                        json_path = os.path.join(root, f"{new_file_name}")
                        json_data = None
                        with open(json_path, 'r', encoding='utf-8') as json_file:
                            json_data = json.load(json_file)
                            json_data['docName'] = normalize_whitespace(remove_digit_prefix(os.path.splitext(normalize_filename)[0]))
                        with open(json_path, 'w', encoding='utf-8') as json_file:
                            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    print("Modified Files:")
    for original, new in modified_files:
        print(f"'{original}' -> '{new}'")

    print("\nModified JSONs:")
    for original, new in modified_jsons:
        print(f"'{original}' -> '{new}'")

# 示例用法:
process_directory("/Users/zhangfan/Downloads/resum")
