import json
import os


def validate_catagroy_names(data):
    valid_types = {"编", "分编", "章", "节", "条"}

    if isinstance(data, dict):
        # If 'type' is in the dictionary, check its value
        if "type" in data:
            if data["type"] not in valid_types:
                return False
        if "categoryName" in data:
            if data["categoryName"] not in valid_types:
                return False
        # Recursively check all children if they exist
        if "children" in data:
            for child in data["children"]:
                if not validate_catagroy_names(child):
                    return False
    return True


def valid_non_leaf_content(data):
    if isinstance(data, dict):
        # Check if the node is a leaf node (does not have 'children')
        is_leaf = "children" not in data

        # If it's not a leaf and has 'content', return False
        if not is_leaf and "content" in data:
            return False

        # Recursively check all children if they exist
        if "children" in data:
            for child in data["children"]:
                if not valid_non_leaf_content(child):
                    return False

    return True

def valid_leaf_nodes(data, file_path):
    """
    检查 JSON 数据中的叶子节点，确保它们包含 'scenarios_summary' 和 'scenarios' 字段。
    """
    if isinstance(data, dict):
        if "children" not in data:  # Check if it's a leaf node
            missing_fields = []
            if "scenarios_summary" not in data:
                missing_fields.append("scenarios_summary")
            if "scenarios" not in data:
                missing_fields.append("scenarios")

            if missing_fields:
                return False

        # Recursively check all children if they exist
        if "children" in data:
            for child in data["children"]:
                return valid_leaf_nodes(child, file_path)
            
def transform_categorytype_key(data):
    """
    将JSON结构转换为指定格式：
    - 将 'type' 字段重命名为 'categoryName'。
    - 如果是叶子节点（没有 'children' 字段），
      删除 'categoryName' 字段。
    """
    if isinstance(data, dict):
        new_data = {}
        transformed = False
        for key, value in data.items():
            if key == "type":
                # Rename 'type' to 'categoryName'
                new_data["categoryName"] = value
                transformed = True
            elif key == "children":
                # Recursively transform each child
                new_data[key] = [transform_categorytype_key(child) for child in value]
            else:
                new_data[key] = value

        # Remove 'categoryName' if it's a leaf node at level 5 (type 条)
        if "children" not in new_data:
            if "categoryName" in new_data:
                del new_data["categoryName"]
            if "type" in new_data:
                del new_data["type"]

        return new_data

    return data


def fix_pathname(node, parent_pathname=""):
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

    # 递归处理子节点
    if "children" in node:
        for child in node["children"]:
            fix_pathname(child, node["pathname"])

    return node


def transform_category_name(data):
    """
    对所有非叶子节点的 'content' 字段进行以下操作：
    - 如果存在 'content'，将其 key 重命名为 'name'。
    - 删除 value 中前后的空格、中文标点符号。
    """
    if isinstance(data, dict):
        # Check if the node is a leaf node (does not have 'children')
        is_leaf = "children" not in data

        # If it's not a leaf and has 'content', rename it to 'name'
        if not is_leaf and "content" in data:
            # Clean up the 'content' value
            content_value = data["content"]
            cleaned_value = content_value.strip(" ，。、：；")

            # Rename 'content' to 'name'
            data["name"] = cleaned_value

            # Remove the original 'content' field
            del data["content"]

        # Recursively process all children if they exist
        if "children" in data:
            for child in data["children"]:
                transform_category_name(child)

    return data





def valid_non_leaf_content_dir(directory):
    """
    遍历指定目录下所有JSON文件，更新其内容以包含生成的pathname。
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 使用generate_pathname函数更新数据
                ret = valid_non_leaf_content(data)
                if not ret:
                    print(f"Invalid content in non-leaf node in file: {file_path}")
                    data = transform_category_name(data)
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)


def valid_leaf_nodes_dir(directory_path):
    """
    递归遍历目录及其子目录下的所有 JSON 文件，检查叶子节点的字段。
    """
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not valid_leaf_nodes(data, file_path):
                        print(f"文件 {file_path} 不是合法的 JSON 格式: {e}")
                        continue


def fix_pathname_dir(directory):
    """
    遍历指定目录下所有JSON文件，更新其内容以包含生成的pathname。
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 使用generate_pathname函数更新数据
                updated_data = fix_pathname(data)

                # 将更新后的数据写回到文件中
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(updated_data, f, ensure_ascii=False, indent=4)


def transfrom_categoryname_dir(directory):
    """
    遍历指定目录下所有JSON文件，更新其内容以包含生成的pathname。
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not validate_catagroy_names(data):
                    print(f"Invalid JSON structure in file: {file_path}")
                # 使用generate_pathname函数更新数据
                updated_data = transform_categorytype_key(data)

                # 将更新后的数据写回到文件中
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(updated_data, f, ensure_ascii=False, indent=4)

def update_file_extensions(directory):
    """
    遍历指定目录下所有文件，将特定扩展名的文件重命名为 .json 格式。
    该函数会将所有以 .docx.json、.doc.json 或 .pdf.json 结尾的文件重命名为 .json 格式。
    """
    # Compile a case-insensitive regular expression pattern for matching specific file extensions
    pattern = re.compile(r"\.(docx|doc|pdf)\.json$", re.IGNORECASE)

    # Walk through the directory
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Check if the file matches the pattern
            if pattern.search(file):
                # Create the new file name by replacing the matched pattern with ".json"
                new_file = pattern.sub(".json", file)
                # Construct full path for the old and new file names
                old_file_path = os.path.join(root, file)
                new_file_path = os.path.join(root, new_file)

                # Rename the file
                os.rename(old_file_path, new_file_path)
# 示例调用
DIR = "/Users/zhangfan/Downloads/resum"
# transfrom_categoryname_in_directory(DIR)
# fix_pathname_in_directory(DIR)
# update_file_extensions(DIR)
# check_non_leaf_content_in_directory(DIR)

# update_file_extensions('/Users/zhangfan/Downloads/resum')
valid_leaf_nodes_dir("/Users/zhangfan/work/省厅/dsx/projects/law-agent/laws/parsed_laws")
