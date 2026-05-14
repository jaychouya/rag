import re
from difflib import SequenceMatcher
from typing import List


def normalize_whitespace(text: str) -> str:
    special_spaces = ["\xa0", "\u3000"]
    for space in special_spaces:
        text = text.replace(space, " ")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()
    return text


def getTextSimilarity(a: str, b: str, str2remove: list[str] = [], threshold: float = 0.99) -> float:
    if a == b:
        return 1
    a = normalize_whitespace(a)
    b = normalize_whitespace(b)
    for s in str2remove:
        a = a.replace(s, "")
        b = b.replace(s, "")
    if a == b:
        return 1
    return SequenceMatcher(None, a, b).ratio()


def isSimilarText(a: str, b: str, str2remove: list[str] = [], threshold: float = 0.99) -> bool:
    return getTextSimilarity(a, b, str2remove) >= threshold


def split_batch_by_textlen(
    entrys, text_key_name: str | list[str], max_batch_size=10, max_text_length=4000
) -> list[list[dict]]:
    result = []
    current_batch = []
    current_length = 0

    for entry in entrys:
        if isinstance(text_key_name, str):
            summary_length = len(entry.get(text_key_name, ""))
        else:
            summary_length = sum(len(entry.get(key, "")) for key in text_key_name)

        if max_batch_size is not None and len(current_batch) >= max_batch_size:
            result.append(current_batch)
            current_batch = []
            current_length = 0

        if current_length + summary_length > max_text_length and current_batch:
            result.append(current_batch)
            current_batch = []
            current_length = 0

        current_batch.append(entry)
        current_length += summary_length

    if current_batch:
        result.append(current_batch)

    return result
