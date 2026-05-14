import csv
import json


def convert_json_to_csv():
    # 读取JSON文件
    json_file_path = 'all_category.json'
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 准备category数据
    category_data = []
    # 准备law数据
    law_data = []
    
    # 遍历JSON数据
    for type_item in data:
        type_name = type_item['type']
        categories = type_item['categories']
        
        for category in categories:
            category_name = category['name']
            summary = category['summary']
            
            # 添加到category数据
            category_data.append({
                'name': category_name,
                'summary': summary,
                'type': type_name
            })
            
            # 处理该category下的laws
            laws = category.get('laws', [])
            for law in laws:
                law_data.append({
                    'law_name': law,
                    'category_name': category_name
                })
    
    # 写入category.csv
    with open('category.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['name', 'summary', 'type']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(category_data)
    
    # 写入law.csv
    with open('law.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['law_name', 'category_name']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(law_data)
    
    print(f"成功生成 category.csv，包含 {len(category_data)} 条记录")
    print(f"成功生成 law.csv，包含 {len(law_data)} 条记录")

if __name__ == "__main__":
    convert_json_to_csv()
