import os
import re
from typing import Any, Dict, List, Union


def replace_env_vars(value: str) -> str:
    if not isinstance(value, str):
        return value

    def replace_var(match):
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default_value = var_expr.split(":-", 1)
            return os.getenv(var_name, default_value)
        env_value = os.getenv(var_expr)
        if env_value is None:
            raise ValueError(f"环境变量 {var_expr} 未设置")
        return env_value

    return re.sub(r"\$\{([^}]+)\}", replace_var, value)


def convert_value_type(key: str, value: str) -> Any:
    boolean_keys = {"enabled", "debug_mode", "strict_mode"}
    if key in boolean_keys:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return value

    integer_keys = {"port", "max_tokens", "context_window_len", "timeout", "retry_count", "max_history_count"}
    if key in integer_keys:
        if isinstance(value, str):
            return int(value)
        return value

    float_keys = {"temperature"}
    if key in float_keys:
        if isinstance(value, str):
            return float(value)
        return value

    return value


def process_env_vars(config: Union[Dict[str, Any], List, Any]) -> Any:
    if isinstance(config, dict):
        processed = {}
        for key, value in config.items():
            if isinstance(value, dict):
                processed[key] = process_env_vars(value)
            elif isinstance(value, list):
                processed[key] = [
                    process_env_vars(item) if isinstance(item, (dict, list)) else item
                    for item in value
                ]
            elif isinstance(value, str):
                replaced_value = replace_env_vars(value)
                processed[key] = convert_value_type(key, replaced_value)
            else:
                processed[key] = value
        return processed
    elif isinstance(config, list):
        return [process_env_vars(item) for item in config]
    else:
        return config
