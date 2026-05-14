import asyncio
import json
import os
import sys

_app = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if _app not in sys.path:
    sys.path.insert(0, _app)

from law_finder.finder import query_law_by_case_info

# 民法典1060
# CASE = """
# 小刘与妻子对孩子的教育理念不同，妻子主张“精英式培养”，小刘则认为不能过度教育。暑假期间，妻子瞒着小刘给孩子报了近2万元的课外培训班。小刘得知后很生气，认为培训合同未经他同意，应认定为无效，要求培训机构退费，遭到拒绝，一气之下诉至法院
# """
# 民法典1077
# CASE = """
# 小张与妻子都是火爆脾气，结婚后争吵不断。一次大吵过后，两人怒气冲冲地来到民政局登记离婚。工作人员告知两人关于离婚冷静期的相关规定，要求他们30天之后再来办手续。还不到30天，两人便怒气消散，又重归于好，便没有再去办离婚手续。
# """

# 民法典1064
# CASE = """
# 常某与丈夫王某离婚后，一债主同时将两人告上法庭，称王某在婚内向其借款数万元，要求两人共同承担还款责任。法院查明，该笔借款被王某用于打赏网络主播，不属于夫妻共同债务，判决由王某个人承担还款责任。
# """

# 民法典1084
# CASE = """
# 徐某（男）与李某（女）婚后育有一子（1岁半）、一女（8岁），两人准备离婚，都想争取孩子抚养权。徐某经济状况较好，工资收入是李某的数倍，认为自己胜券在握。李某虽收入不高，但女儿更愿意随其生活。法院最终判决，儿子、女儿抚养权均归李某，徐某按照其月收入的40%给付李某抚养费。
# """

# 民法典183
CASE = """
2023年12月，柴某与顾某共同乘坐轨道交通七号线镇坪路站上行自动扶梯，顾某位于柴某前方。电梯上行过程中，顾某站立不稳向后摔倒时，因柴某及时救助而未倒，但柴某为救助顾某而受伤。柴某于受伤当天自行前往医院就医，诊断为左跟骨前外缘撕脱骨折，左足、左踝退行性改变。因救助顾某的行为，上海市普陀区委员会宣传部于2023年12月向柴某颁发“普陀好人-见义勇为”证书。后柴某向法院起诉，请求判令顾某赔偿其因救助顾某受伤产生的医药费等损失7992.68元。
"""

CASE = """
2023年5月1日，张三投诉民警李某在上个月办案过程中，暴力殴打和辱骂其妈妈. 张三想要知道李某违反了警察法哪些法规
"""


def callback(message, msg_type="message"):
    if msg_type == "message":
        print(message)
    else:
        print(f"<{msg_type}>{message}</{msg_type}>")


CASE = """
2023年5月1日，张三驾驶小型汽车在市区道路上行驶时，因未注意观察前方交通情况，导致与前方停靠的
公交车发生碰撞，造成张三受伤，车辆损坏。经交警部门认定，张三在事故中负主要责任，公交车司机负次要责任。
事故发生后，张三向保险公司申请理赔，但保险公司以张三违反交通规则为由拒绝理赔。遂张三认为交警判罚不合理，向交警部门发起行政复议。
"""
CASE = """
张某父母育有三名子女，2013年父亲去世，未立遗嘱，2015年母亲去世前，在两位好友的见证下，以录像方式立下遗嘱，表示在自己生病期间张某一直尽心照料，决定把一套房产留给张某，存款12万元则留给张某的两个姐姐。张某的两个姐姐认为录像形式的遗嘱并非有效遗嘱，父母遗产应该按法定继承方式分割, 请查找相关法律并给出解释。
"""
#CASE = """看看民法典的1024条以及警察法第一章第二节都分别在说什么"""


if __name__ == "__main__":
    result = asyncio.run(query_law_by_case_info(CASE, max_llm_threads=8, progressCallback=callback))
    print(json.dumps(result, ensure_ascii=False, indent=2))
# #CASE = """我要和我老婆离婚，孩子两岁，我想要争取孩子的抚养权，我老婆收入不高，孩子更愿意跟着我生活。请问我应该如何准备材料和证据？"""
# #CASE = """看看民法典婚姻、物权第一章的内容、以及第1024条的内容，还有警察法第一章，以及警察法20条的内容。"""
# # CASE = """看看民法典和警察法都分别在说什么"""
# # 提取案件查询信息
# case_info = parse_case(case=CASE, findingMessageCallback=callback)
# if not case_info:
#     callback("未能提取案件信息，请检查案件描述是否符合要求", msg_type="warning")
#     exit()

# indicated_laws = None  # 指定的法规
# indicated_articles = []  # 指定的条款
# indicated_sections = []  # 指定的章节

# law_scopes = ([], [])  # 分为两类，一类是直接查询精准条款的，一类是需要使用LLM进行路径匹配的
# if case_info.get("law_scope"):
#     indicated_laws = parse_law_path(case_info["law_scope"])
#     if not indicated_laws is None:
#         # 提取path中，unit="条"的条目，并直接查询，
#         laws = load_laws([law["id"] for law in indicated_laws])
#         for l1 in indicated_laws:
#             for l2 in laws:
#                 if l1["id"] == l2["id"]:
#                     l1["content"] = l2["content"]
#                     break

#         law_scopes = split_path_type(indicated_laws)
# indicated_articles = find_law_by_article_path(law_scopes[0]) if law_scopes[0] else []

# result = None
# if case_info.get("query_method", "law_info") == "law_info":
#     indicated_sections = await find_law_by_path(law_scopes[1])
#     result = []
#     result.extend(indicated_articles)
#     result.extend(indicated_sections)
#     jinjaTpl_path = os.path.join(os.path.dirname(__file__), "law_finder/templates", "sumary_lawinfo_prompt.jinja2")
#     jinjaEnv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(jinjaTpl_path)))
#     jinjaTpl = jinjaEnv.get_template(os.path.basename(jinjaTpl_path))  # 渲染模板
#     summary_prompt = jinjaTpl.render(question=CASE, law_infos=result)
    
# else:
#     jinjaTpl_path = os.path.join(os.path.dirname(__file__), "law_finder/templates", "case_prompt.jinja2")
#     jinjaEnv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(jinjaTpl_path)))
#     jinjaTpl = jinjaEnv.get_template(os.path.basename(jinjaTpl_path))  # 渲染模板
#     case_prompt = jinjaTpl.render(case_info=case_info, law_scope=law_scopes[1])
    
#     laws = []
#     lawids = []
#     if law_scopes[1]:
#         # id去重
#         lawids = list(set([law["id"] for law in law_scopes[1]]))
#     else:
#         categories = find_categories(case_prompt, scoreThreshold=4, findingMessageCallback=callback)
#         message = f"# 根据案件事实，找到相关的法律条款类型：\n"
#         for category in categories:
#             message += f"+ {category['type']}-{category['name']}\n"
#         callback(message)
#         laws = find_laws(categories, case=case_prompt, scoreThreshold=4, findingMessageCallback=callback)
#         laws = laws.get("laws", [])
#         lawids = list(set([law["id"] for law in laws]))
    
#     laws = load_laws(lawids)
#     messages = "# 将从以下法规中进行查询：\n"
#     for law in law_scopes[1]:
#         messages += f"+ {law['name']}\n"
#     callback(messages)
    
#     result = find_article([l['content'] for l in laws], case=case_prompt, findingMessageCallback=callback)
#     jinjaTpl_path = os.path.join(os.path.dirname(__file__), "law_finder/templates", "summary_case_and_law_prompt.jinja2")
#     jinjaEnv = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(jinjaTpl_path)))
#     jinjaTpl = jinjaEnv.get_template(os.path.basename(jinjaTpl_path))  # 渲染模板
#     summary_prompt = jinjaTpl.render(question=CASE, law_infos=result['laws'])

# # 调用大模型回复
# exit()
# # {case_info['contention']}\n+ 相关人员：{case_info['relations']}
# case_prompt = f"+ 案件简述：{case_info['summary']}\n"
# case_prompt += f"+ 相关人员：{', '.join(case_info.get('relations', []))}\n"
# contention = case_info.get("contention", [])
# if not contention:
#     case_prompt += "+ 争议焦点：不明确\n"
# elif len(contention) == 1:
#     case_prompt += f"+ 争议焦点：{contention[0]}\n"
# else:
#     case_prompt += f"+ 争议焦点：\n"
#     for i, cont in enumerate(contention):
#         case_prompt += f"  {i+1}. {cont}\n"
# case_prompt += f"+ 案件关键词：{', '.join(case_info.get('keywords', []))}\n"
# if case_info.get("query"):
#     case_prompt += f"+ **用户查询需求：{case_info['query']}\n"
# if law_scopes[1]:
#     case_prompt += f"+ **仅从以下范围中进行查询**：\n"
#     for scope in indicated_laws:
#         if scope.get("path_summary"):
#             case_prompt += f"  - {scope['path_summary']}\n"

# callback(f"案件信息提取完成：\n{case_prompt}")
# if case_info.get("query_method", "law_info"):
#     print("只查询法规信息")
# else:
#     print("根据案例查询法规及相关条款")
# exit()
# categories = find_categories(case_prompt, scoreThreshold=4, findingMessageCallback=callback)
# message = f"# 根据案件事实，找到相关的法律条款类型：\n"
# for category in categories:
#     message += f"+ {category['type']}-{category['name']}\n"
# callback(message)

# laws = find_laws(categories, case=case_prompt, scoreThreshold=4, findingMessageCallback=callback)
# valuable_laws = laws.get("laws", [])
# other_valuable_laws = laws.get("other_valuable", [])

# result = find_article(valuable_laws, case=case_prompt, findingMessageCallback=callback)

# if not result or not result.get("laws"):
#     callback("未找到相关法律条款", msg_type="warning")
# else:
#     laws = result["laws"]
#     other_valuable = result.get("other_valuable", [])
#     message = f"## 为您找到以下{len(laws)}条相关可参考的法律条款：\n"
#     for law in laws:
#         message += f"### {law['name']}\n"
#         message += f"{law['content']}\n"
#         message += f"#### 适用场景\n> {law['scenarios_summary']}\n"
#         message += f"#### 参考理由\n> {law['reason']}\n"
#     if other_valuable:
#         message += f"\n## 其他可能的参考的法律条款,共{len(other_valuable)}条\n"
#         for law in other_valuable:
#             message += f"### {law['name']}\n"
#             message += f"{law['content']}\n"
#             message += f"#### 参考理由\n> {law['reason']}\n"
#     callback(message)
