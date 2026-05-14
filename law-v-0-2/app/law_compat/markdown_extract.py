import json
import re
from typing import Optional


def extract_all_json_from_markdown(jsonStr):
    jsonStr = jsonStr.strip()
    jsonStr = re.sub(r"<think>.*?</think>", "", jsonStr, flags=re.DOTALL)
    jsonStr = re.sub(r"<detail>.*?</detail>", "", jsonStr, flags=re.DOTALL)
    jsonStr = re.sub(r"<summary>.*?</summary>", "", jsonStr, flags=re.DOTALL)

    matches = []
    lines = jsonStr.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("```json"):
            json_content = []
            i += 1
            while i < len(lines):
                current_line = lines[i]
                if current_line.strip() == "```":
                    break
                json_content.append(current_line)
                i += 1

            if i < len(lines):
                matches.append("\n".join(json_content))
        i += 1

    ret = []
    if len(matches) == 0 and jsonStr:
        try:
            ret = [json.loads(jsonStr)]
        except json.JSONDecodeError:
            print("没有找到json格式的内容")
    else:
        for match in matches:
            jsonStr = match.strip()
            if not jsonStr:
                continue
            jsonStr = re.sub(r"\s+", " ", jsonStr)
            jsonStr = jsonStr.replace("，", ",").replace("：", ":")
            jsonStr = jsonStr.replace("【", "[").replace("】", "]")
            try:
                ret.append(json.loads(jsonStr))
            except json.JSONDecodeError as e:
                print(f"解析JSON失败: {e}\n{matches}")

    for i in range(len(ret)):
        if isinstance(ret[i], dict):
            for key, value in ret[i].items():
                if isinstance(value, str) and (value == "null" or value == '"null"'):
                    ret[i][key] = None
        elif isinstance(ret[i], list):
            for j in range(len(ret[i])):
                if isinstance(ret[i][j], str) and (ret[i][j] == "null" or ret[i][j] == '"null"'):
                    ret[i][j] = None
    return ret


def extract_python_from_markdown(response: str) -> Optional[str]:
    python_pattern = r"```python\s*(.*?)\s*```"
    matches = re.findall(python_pattern, response, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    code_pattern = r"```\s*(.*?)\s*```"
    matches = re.findall(code_pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

    return None


def extract_sql_from_markdown(response: str) -> Optional[str]:
    sql_pattern = r"```sql\s*(.*?)\s*```"
    matches = re.findall(sql_pattern, response, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    lines = response.strip().split("\n")
    sql_lines = []
    in_sql = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if any(line.upper().startswith(keyword) for keyword in ["SELECT", "CREATE", "INSERT", "UPDATE", "DELETE"]):
            in_sql = True
            sql_lines.append(line)
        elif in_sql:
            if line.endswith(";"):
                sql_lines.append(line)
                break
            else:
                sql_lines.append(line)

    if sql_lines:
        return "\n".join(sql_lines)

    return None
