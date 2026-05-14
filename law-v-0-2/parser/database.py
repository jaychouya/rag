import json
import os

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from law_compat.mysql_connect import closeConnect, openConnect
from tqdm import tqdm


# 插入单挑法律json文件
def insert_or_update_legal_data(file_path, categories):
    # 首先读取 file-path并验证其有效性: 必须有 summary, docName, scenarios_summary, subjects这几个字段
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            data = json.load(file)
            required_fields = ['summary', 'docName', 'scenarios_summary', 'subjects']
            for field in required_fields:
                if field not in data:
                    raise Exception(f"无效的法律文件: {file_path} 缺少字段: {field}")
        except Exception as e:
            raise ValueError(f"无效的法律文件: {file_path}\n错误信息: {e}")
    
    """
    按照这个规则将其插入数据库
    category_id: 先categories中遍历所有的category，每个category的对象里面有一个laws数组，如果docName在这个数组中，就取出这个category的id
    summary = data['summary']
    scenarios = data['scenarios_summary']
    subjects = data['subjects']
    rule_category = data['rule_category']
    rule_form = data['rule_form']
    rule_content_type = data['rule_content_type']
    tags = []
    title = data['docName']
    """
    # 验证 categories 是否有效
    if not isinstance(categories, list) or not all(isinstance(cat, dict) for cat in categories):
        raise ValueError("Invalid categories format. It should be a list of dictionaries.")
    # 验证每个 category 是否包含 'id' 和 'laws' 字段
    for category in categories:
        if 'id' not in category or 'laws' not in category:
            raise ValueError(f"Invalid category format: {category}. Each category must contain 'id' and 'laws' fields.")
    # 获取文件名的父目录作为 bussiness
    title = data['docName']
    # 获取 category_id
    category_id = None
    type = None
    for category in categories:
        if title in category['laws']:
            category_id = category['id']
            type = category['type']  # 获取类型
            break
    if category_id is None:
        print(f"[Error]Document '{file_path}' not found in any category's laws.")
        return
    # 获取其他字段
    summary = data['summary']
    scenarios = data['scenarios_summary']
    subjects = data['subjects']
    rule_category = data.get('rule_category', '')
    rule_form = data.get('rule_form', '')
    rule_content_type = data.get('rule_content_type', '')
    content = json.dumps(data, ensure_ascii=False)  # 将整个 JSON 对象作为 content
    # 打开数据库连接，更新或者插入， 如果是更新，其他字段都直接更新，但是tags（json格式）要追加并去重
    connection = openConnect(dbName='law', autocommit=True)
    cursor = connection.cursor()
    # 检查是否已有同名记录
    query_check = "SELECT tags, id FROM LegalDocuments WHERE name = %s"
    cursor.execute(query_check, (title,))
    result = cursor.fetchone()
    if result:  # 如果存在同名记录，更新其他字段
        existing_tags = json.loads(result[0]) if result[0] else []
        # 追加新的 tags 并去重
        new_tags = list(set(existing_tags + [type, data['rule_category']]))
        new_tags_json = json.dumps(new_tags, ensure_ascii=False)
        query_update = """
        UPDATE LegalDocuments 
        SET category_id = %s, summary = %s, scenarios = %s, subjects = %s,
            rule_category = %s, rule_form = %s, rule_content_type = %s, tags = %s, content = %s 
        WHERE id = %s
        """
        cursor.execute(query_update, (category_id, summary, scenarios, subjects,
                                      rule_category, rule_form, rule_content_type, new_tags_json, content, result[1]))
        print(f"Warning: Updated existing record for '{title}' from {file_path}")
    else:  # 否则插入新记录
        tags = json.dumps([type, data['rule_category']], ensure_ascii=False)  # 将父目录名作为第一个标签
        query_insert = """
        INSERT INTO LegalDocuments (category_id, summary, scenarios, subjects,
                                    rule_category, rule_form, rule_content_type, tags, name, content)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query_insert, (category_id, summary, scenarios, subjects,
                                      rule_category, rule_form, rule_content_type, tags, title, content))

    # 关闭连接
    closeConnect(connection)

def load_categories_from_json(category_json_files: list):
    all_categories = []
    for category_file in category_json_files:
        with open(category_file, 'r', encoding='utf-8') as file:
            categories_types = json.load(file)
            for cat_type in categories_types:
                type_name = cat_type['type']
                categories = cat_type['categories']
                for cat in categories:
                    all_categories.append({
                        'type': type_name,
                        'summary': cat['summary'],
                        'name': cat['name'],
                        'laws': cat['laws'],
                    })
    return all_categories

def update_categories(category_json_files: list):
    # 读取所有的category_json_files（每一个是一个数组），然后合并所有的数组
    all_categories = load_categories_from_json(category_json_files)
    # 检查数组中 每一个对象的”category“字段是否有重复
    unique_categories = set()
    unique_laws = set()
    for category in all_categories:
        if category['name'] in unique_categories:
            raise ValueError(f"Duplicate category found: {category['name']}")
        else:
            unique_categories.add(category['name'])
        for law in category['laws']:
            if law in unique_laws:
                raise ValueError(f"Duplicate law found: {law} in category {category['name']}")
            else:
                unique_laws.add(law)

    # 打开数据库连接
    connection = openConnect(dbName='law', autocommit=True)
    cursor = connection.cursor()
    # 
    # 如果LegalCategory对应的name有，则update，否则 insert
    # 查询名字
    cursor.execute("SELECT id, name FROM LegalCategory")
    existing_categories = {row[1]: row[0] for row in cursor.fetchall()}
    # 遍历所有的category， 如果name在existing_categories中，则更新，否则插入
    for category in all_categories:
        if category['name'] in existing_categories:
            # 更新
            cursor.execute(
                "UPDATE LegalCategory SET type = %s, summary = %s WHERE name = %s",
                (json.dumps([category['type']], ensure_ascii=False), category['summary'], category['name'])
            )
        else:
            # 插入
            cursor.execute(
                "INSERT INTO LegalCategory (type, name, summary) VALUES (%s, %s, %s)",
                (json.dumps([category['type']], ensure_ascii=False), category['name'], category['summary'])
            )
    # 关闭连接
    closeConnect(connection)

def query_category_ids(category_json_files: list):
    # 读取所有的category_json_files（每一个是一个数组），然后合并所有的数组
    all_categories = load_categories_from_json(category_json_files)

    # 打开数据库连接
    connection = openConnect(dbName='law', autocommit=True)
    cursor = connection.cursor()

    for category in all_categories:
        cursor.execute("SELECT id FROM LegalCategory WHERE name = %s", (category['name'],))
        result = cursor.fetchone()
        if result:
            category['id'] = result[0]
        else:
            raise ValueError(f"Category '{category['name']}' not found in database.")

    # 关闭连接
    closeConnect(connection)
    return all_categories
# 清空并更新分类信息
update_categories(['laws/category/all_category.json'])

# 将一个目录下的所有法律文件插入到数据库中， 首先先获取categories，然后再插入所有的法律文件
CATEGORY_BASEDIR = 'laws/category'
CATEGORIES = ['all_category.json']
PARSED_LAWS_DIR = 'laws/parsed_laws'
def insert_all_legal_data_from_directory(law_path, category_json_files=None):
    total_files = 0
    for root, dirs, files in os.walk(law_path):
        for file_name in files:
            if file_name.endswith('.json'):
                total_files += 1
    # 查询categories
    categories = query_category_ids(category_json_files)
    pbar = tqdm(total=total_files, desc="Inserting legal documents")
    # 插入法律文件
    for root, dirs, files in os.walk(law_path):
        for file_name in files:
            if file_name.endswith('.json'):
                file_path = os.path.join(root, file_name)
                insert_or_update_legal_data(file_path, categories)
                pbar.update(1)
    pbar.close()

insert_all_legal_data_from_directory(law_path = PARSED_LAWS_DIR, category_json_files=[os.path.join(CATEGORY_BASEDIR, cat) for cat in CATEGORIES])
