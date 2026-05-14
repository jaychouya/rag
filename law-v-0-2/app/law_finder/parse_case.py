# 通过案例查找目录及其中的法规
from typing import Callable, Optional

from law_finder.jinja_env import get_template
from law_finder.myextractor import CodeExtractor

from .llm import LLMSDK


# 根据用户需求分析要素
def parse_case(case, findingMessageCallback: Optional[Callable[[str], None]] = None) -> Optional[dict]:
    extract_sevice = CodeExtractor(
        llm=LLMSDK,
        title="parse_case",
    )
    message = get_template("parse_case.jinja2").render({"case": case})

    ret = extract_sevice.do_sync(message=message)
    if not isinstance(ret, dict):
        return None
    return ret
