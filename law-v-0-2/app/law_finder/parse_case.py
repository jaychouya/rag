# 通过案例查找目录及其中的法规
from typing import Callable, Optional

from law_finder.jinja_env import get_template
from law_finder.myextractor import CodeExtractor

from .llm import LLMSDK


async def parse_case(case, findingMessageCallback: Optional[Callable[[str], None]] = None) -> Optional[dict]:
    if findingMessageCallback:
        findingMessageCallback("正在分析案件信息...\n")
    extract_sevice = CodeExtractor(
        llm=LLMSDK,
        title="parse_case",
        max_retry=2,
        call_timeout=90.0,
    )
    message = get_template("parse_case.jinja2").render({"case": case})
    ret = await extract_sevice.do(message=message)
    if not isinstance(ret, dict):
        return None
    return ret
