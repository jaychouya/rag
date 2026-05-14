#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
from typing import Dict, Tuple

# 审计法规分类定义
SJ_CATEGORIES = {
    "审计监督与执法": {
        "summary": "涵盖国家审计监督制度、审计执法程序、审计机关职责权限等核心审计法律法规，是审计工作的基础性法律框架。",
        "keywords": ["审计法", "审计监督", "审计机关", "审计执法", "审计准则", "审计制度", "审计全覆盖", "经济责任审计", "内部审计"]
    },
    "政府采购与招投标": {
        "summary": "规范政府采购行为、招投标程序、采购资金管理等相关法规，确保政府采购活动的规范性和透明度。",
        "keywords": ["政府采购", "招投标", "采购法", "采购管理", "采购监督", "采购程序", "采购资金", "采购合同", "采购方式"]
    },
    "财务管理与会计规范": {
        "summary": "涉及财务管理、会计核算、会计监督、财务制度等基础性财务法规，为审计工作提供财务规范依据。",
        "keywords": ["会计法", "财务管理", "会计核算", "会计制度", "财务规则", "会计基础", "会计档案", "财务预算", "财务决算", "财务收支"]
    },
    "财政监督与处罚": {
        "summary": "规范财政违法行为处罚、财政监督、财政资金管理等相关法规，维护国家财政经济秩序。",
        "keywords": ["财政违法", "财政监督", "财政处罚", "财政处分", "财政资金", "财政收支", "财政票据", "财政管理", "财政制度"]
    }
}

def load_law_data(law_name: str) -> Dict:
    """加载法规JSON数据"""
    json_path = f"../../laws/parsed_laws/审计/{law_name}.json"
    if not os.path.exists(json_path):
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载 {law_name} 失败: {e}")
        return None

def extract_summary_and_scenarios(data: Dict) -> Tuple[str, str]:
    """提取法规的summary和scenarios_summary"""
    summary = ""
    scenarios_summary = ""
    
    if not data or 'children' not in data:
        return summary, scenarios_summary
    
    # 递归查找summary和scenarios_summary
    def find_summaries(children):
        nonlocal summary, scenarios_summary
        for child in children:
            if 'summary' in child and not summary:
                summary = child['summary']
            if 'scenarios_summary' in child and not scenarios_summary:
                scenarios_summary = child['scenarios_summary']
            if 'children' in child:
                find_summaries(child['children'])
    
    find_summaries(data['children'])
    return summary, scenarios_summary

def classify_law(law_name: str, summary: str, scenarios_summary: str) -> str:
    """根据法规名称和内容进行分类"""
    content = f"{law_name} {summary} {scenarios_summary}".lower()
    
    # 计算每个分类的匹配分数
    scores = {}
    for category, info in SJ_CATEGORIES.items():
        score = 0
        for keyword in info['keywords']:
            if keyword.lower() in content:
                score += 1
        scores[category] = score
    
    # 返回得分最高的分类
    if scores:
        return max(scores, key=scores.get)
    
    # 如果没有明确匹配，根据法规名称进行判断
    if "审计" in law_name:
        return "审计监督与执法"
    elif "采购" in law_name or "招标" in law_name:
        return "政府采购与招投标"
    elif "会计" in law_name or "财务" in law_name:
        return "财务管理与会计规范"
    elif "财政" in law_name:
        return "财政监督与处罚"
    else:
        return "审计监督与执法"  # 默认分类

def main():
    """主函数"""
    print("开始分析审计法规并生成分类...")
    
    # 从审计.md文件中读取法规列表
    laws = []
    with open("../../laws/parsed_laws/审计.md", 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('+ '):
                law_name = line[2:]  # 去掉 "+ " 前缀
                laws.append(law_name)
    
    print(f"找到 {len(laws)} 个法规")
    
    # 分析每个法规
    categorized_laws = []
    for law_name in laws:
        print(f"分析法规: {law_name}")
        
        # 加载法规数据
        data = load_law_data(law_name)
        if not data:
            print(f"  跳过: 无法加载数据")
            continue
        
        # 提取summary和scenarios_summary
        summary, scenarios_summary = extract_summary_and_scenarios(data)
        
        # 分类
        category = classify_law(law_name, summary, scenarios_summary)
        
        categorized_laws.append({
            'law_name': law_name,
            'category': category,
            'summary': summary,
            'scenarios_summary': scenarios_summary
        })
        
        print(f"  分类: {category}")
    
    # 生成分类统计
    category_stats = {}
    for law in categorized_laws:
        category = law['category']
        if category not in category_stats:
            category_stats[category] = []
        category_stats[category].append(law['law_name'])
    
    print("\n分类统计:")
    for category, laws_list in category_stats.items():
        print(f"  {category}: {len(laws_list)} 个法规")
    
    # 生成sj_category.csv
    print("\n生成 sj_category.csv...")
    with open('sj_category.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'summary', 'type'])
        
        for category, info in SJ_CATEGORIES.items():
            writer.writerow([category, info['summary'], '审计'])
    
    # 生成sj_law.csv
    print("生成 sj_law.csv...")
    with open('sj_law.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['law_name', 'category_name'])
        
        for law in categorized_laws:
            writer.writerow([law['law_name'], law['category']])
    
    print("✅ 分类完成！")
    print(f"  sj_category.csv: {len(SJ_CATEGORIES)} 个分类")
    print(f"  sj_law.csv: {len(categorized_laws)} 个法规")
    
    # 显示详细分类结果
    print("\n详细分类结果:")
    for category, laws_list in category_stats.items():
        print(f"\n{category} ({len(laws_list)} 个):")
        for law_name in laws_list:
            print(f"  - {law_name}")

if __name__ == "__main__":
    main()
