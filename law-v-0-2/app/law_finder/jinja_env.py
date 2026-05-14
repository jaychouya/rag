import os
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


@lru_cache(maxsize=1)
def get_templates_env() -> Environment:
    return Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=False, enable_async=False)


def get_template(name: str):
    return get_templates_env().get_template(name)
