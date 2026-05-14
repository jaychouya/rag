import os


def find_and_delete_duplicate_files(directory):
    # 用于存储文件名（不含后缀）及其完整路径的字典
    file_dict = {}

    # 遍历目录及其子目录
    for root, _, files in os.walk(directory):
        for file_name in files:
            # 去掉后缀名，考虑 .json, .doc.json, .docx.json, 和 .pdf.json 四种情况
            if file_name.endswith('.doc.json'):
                base_name = file_name[:-9]
            elif file_name.endswith('.docx.json'):
                base_name = file_name[:-10]
            elif file_name.endswith('.pdf.json'):
                base_name = file_name[:-9]
            elif file_name.endswith('.json'):
                base_name = file_name[:-5]
            else:
                base_name = file_name

            # 将文件名存入字典
            if base_name in file_dict:
                file_dict[base_name].append(os.path.join(root, file_name))
            else:
                file_dict[base_name] = [os.path.join(root, file_name)]

    # 查找并删除重复的文件名中仅有 .json 后缀的文件
    for base_name, paths in file_dict.items():
        if len(paths) > 1:
            print(f"Duplicate file name: {base_name}")
            json_only_file = None
            for path in paths:
                if path.endswith('.json') and not any(path.endswith(ext) for ext in ['.doc.json', '.docx.json', '.pdf.json']):
                    json_only_file = path
            
            # 删除仅有 .json 后缀的文件
            if json_only_file:
                try:
                    os.remove(json_only_file)
                    print(f"Deleted: {json_only_file}")
                except Exception as e:
                    print(f"Error deleting {json_only_file}: {e}")

# 使用示例
directory_path = "laws/parsed_laws"
find_and_delete_duplicate_files(directory_path)
