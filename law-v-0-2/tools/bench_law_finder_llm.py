"""
LLM 延迟基准：直连 chat 与 find_article（两阶段）墙钟耗时。

用法（智谱示例）:
  set LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
  set LLM_API_KEY=你的key
  set LLM_MODEL=glm-4-flash
  py -3.12 tools/bench_law_finder_llm.py

仅生成模拟报告（不调 API）:
  py -3.12 tools/bench_law_finder_llm.py --mock
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "app", ROOT / "test"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

MOCK_LAW = {
    "docName": "模拟法规",
    "children": [
        {
            "pathname": "模拟法规/第1章/第1条",
            "summary": "立法目的与依据的摘要，用于压测检索与精判。",
            "content": "第一条 为规范模拟行为，根据上位法，制定本法。",
            "level": 5,
        },
        {
            "pathname": "模拟法规/第1章/第2条",
            "summary": "监督员聘任与职责的摘要，易与第一条混淆。",
            "content": "第二条 监督员由主管部门聘任，对执法活动实施监督。",
            "level": 5,
        },
    ],
}


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


async def bench_chat(rounds: int) -> dict:
    from law_finder.llm import LLMSDK

    lat: list[float] = []
    for i in range(rounds):
        t0 = time.perf_counter()
        _ = await LLMSDK.chat([{"role": "user", "content": f"只回复数字{i}"}], system_message=None)
        lat.append((time.perf_counter() - t0) * 1000.0)
    lat.sort()
    return {
        "rounds": rounds,
        "chat_ms_avg": round(statistics.mean(lat), 2),
        "chat_ms_min": round(min(lat), 2),
        "chat_ms_max": round(max(lat), 2),
        "chat_ms_p50": round(_percentile(lat, 50), 2),
        "chat_ms_p95": round(_percentile(lat, 95), 2),
    }


async def bench_find_article(*, legacy: bool) -> dict:
    if legacy:
        os.environ["LAW_FINDER_LEGACY_TREE_LLM"] = "1"
    else:
        os.environ.pop("LAW_FINDER_LEGACY_TREE_LLM", None)
    import law_finder.find_article_bycase as fab

    importlib.reload(fab)
    find_article = fab.find_article

    t0 = time.perf_counter()
    out = await find_article(
        [{"docName": MOCK_LAW["docName"], "children": MOCK_LAW["children"]}],
        case="案情：讨论立法目的与聘任监督的区别，应更贴近立法依据条款。",
        max_llm_threads=2,
        scoreThreshold=3,
        topK=5,
        findingMessageCallback=None,
    )
    dt = (time.perf_counter() - t0) * 1000.0
    return {
        "mode": "legacy_tree_llm" if legacy else "two_stage_flat",
        "find_article_wall_ms": round(dt, 2),
        "result_paths": [x.get("path") for x in out],
        "result_count": len(out),
    }


def mock_report() -> dict:
    return {
        "mode": "mock",
        "note": "未调用真实 API，仅供报表/对比结构示例",
        "env": {
            "LLM_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
            "LLM_MODEL": "glm-4-flash",
        },
        "chat_benchmark": {
            "rounds": 5,
            "chat_ms_avg": 420.0,
            "chat_ms_min": 310.0,
            "chat_ms_max": 580.0,
            "chat_ms_p50": 400.0,
            "chat_ms_p95": 560.0,
        },
        "find_article_benchmark": {
            "find_article_wall_ms": 1850.0,
            "result_paths": ["MockLaw/Chapter1/Article1"],
            "result_count": 1,
        },
        "architecture_note": "两阶段减少树递归 LLM 次数；墙钟受 J1 批次数、J2 Top-K、网络影响。",
    }


async def main_async(args: argparse.Namespace) -> dict:
    if args.mock:
        return mock_report()

    if not os.getenv("LLM_API_KEY"):
        print("缺少 LLM_API_KEY，使用 --mock 生成示例数据，或配置环境变量后重试。", file=sys.stderr)
        sys.exit(2)

    report: dict = {
        "mode": "live",
        "env": {
            "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
            "LLM_MODEL": os.getenv("LLM_MODEL", ""),
            "LLM_API_KEY_set": bool(os.getenv("LLM_API_KEY")),
        },
    }
    report["chat_benchmark"] = await bench_chat(args.chat_rounds)
    if args.find_article:
        if args.both_modes:
            report["find_article_two_stage"] = await bench_find_article(legacy=False)
            report["find_article_legacy"] = await bench_find_article(legacy=True)
            a = report["find_article_two_stage"]["find_article_wall_ms"]
            b = report["find_article_legacy"]["find_article_wall_ms"]
            report["find_article_speed_ratio_legacy_over_two_stage"] = round(b / a, 3) if a else None
        else:
            report["find_article_benchmark"] = await bench_find_article(legacy=args.legacy)
    return report


def _utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="只输出模拟 JSON，不调 API")
    ap.add_argument("--chat-rounds", type=int, default=5, help="直连 chat 重复次数")
    ap.add_argument("--no-find-article", action="store_true", help="跳过 find_article 整链")
    ap.add_argument("--legacy", action="store_true", help="find_article 使用递归旧路径")
    ap.add_argument(
        "--both-modes",
        action="store_true",
        help="先后跑两阶段与 legacy find_article 并输出耗时比（需多一倍 LLM 调用）",
    )
    ap.add_argument("-o", "--output", type=str, default="", help="写入 JSON 文件路径")
    args = ap.parse_args()
    args.find_article = not args.no_find_article
    if args.both_modes and args.legacy:
        print("--both-modes 与 --legacy 不能同时使用", file=sys.stderr)
        sys.exit(1)

    report = asyncio.run(main_async(args))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
