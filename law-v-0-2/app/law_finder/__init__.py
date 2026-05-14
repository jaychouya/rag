_PUBLIC = frozenset(
    {
        "query_law_by_lawpath",
        "query_law_by_case_info",
        "list_all_laws",
        "auto_query",
        "LLMSDK",
        "get_summary_law_result_prompt",
    }
)

__all__ = sorted(_PUBLIC)


def __getattr__(name: str):
    if name not in _PUBLIC:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name == "LLMSDK":
        from law_finder import llm as _llm

        return _llm.LLMSDK
    from law_finder import finder as _finder

    return getattr(_finder, name)
