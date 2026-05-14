# 检索-精判文档 vs 当前实现（审计）

对照 [law-finder-retrieval-judge.md](law-finder-retrieval-judge.md) 与代码（截至本审计）。

## 文档主张

- 检索：多召不漏，混合关键词全文等，放宽候选。
- 精判：一次性全局对比，将候选送入同一轮 LLM，条款间对比；避免逐层递归。
- LLM 调用：从树规模相关降为常数级（相对旧递归树）。

## 实际实现

### find_categories（`find_law_bycase.py`）

- 对类目 `summary` 做 `split_batch_by_textlen` 分批，每批一次 `CodeExtractor.do`（LLM）。
- **LLM 批次数 = 批次数**，与类目总量相关，非 O(1)。

### find_laws（`find_law_bycase.py`）

- 先 `load_laws_by_category` 得法规候选，再按 `summary` 分批，每批一次 LLM。
- **LLM 批次数 = 法规批次数**，与候选法规数相关。

### find_article（`find_article_bycase.py`）

- **默认**（未设置 `LAW_FINDER_LEGACY_TREE_LLM`）：**两阶段** `_find_article_async_two_stage`。
  - **J1**：扁平化节点后多批 LLM（`j1_batches`），每批打分 idx。
  - **J2**：对 J1 Top-K（`LAW_FINDER_J2_TOP`，默认 20）**再 1 次** LLM 全局对比（`find_article_j2.jinja2`）。
  - 相对「每层递归再开 LLM」，已是**扁平 + 末段一次全局精判**，但 **J1 仍多批**，整体不是「单轮单请求」常数。
- **Legacy 模式**（`LAW_FINDER_LEGACY_TREE_LLM=true`）：批处理 + **子树递归** `_find_article_async_legacy`，与文档「消除递归」不一致。

## 结论

| 文档点 | 是否对齐 |
|--------|----------|
| 检索多召 | 部分对齐（FTS + 结构化 + wiki 并集等） |
| 精判单次全局 | **部分对齐**：J2 为全局对比；J1 仍多批；每部法规并行任务 |
| LLM 与树规模解耦 | **相对 legacy 对齐**；绝对调用次数仍随类目批数、法规批数、法规部数、J1 批数变化 |

后续优化若要严格贴近文档，需压缩或合并 **J1 多批**、**find_laws/find_categories 多批**，并明确上限与度量（见运行指标日志）。

## 运行时可观测指标与配置（实现侧）

一次 `query_law_by_case_info` 结束会打 `law_match_metrics` JSON 日志，字段包含（有则出现）：

- `find_categories_batches` / `find_categories_llm_calls` / `find_categories_pool`
- `find_laws_candidate_count` / `find_laws_batches` / `find_laws_llm_calls`
- `retrieval_id_count` / `retrieval_merge_mode`
- `wiki_hits` / `wiki_doc_ids` / `petition_mode`
- `j1_batches_total` / `j2_llm_calls_total` / `find_article_parallel_laws` / `legacy_initial_batches_total`

环境变量：

| 变量 | 默认 | 含义 |
|------|------|------|
| `LAW_FINDER_RETRIEVAL_DOC_MERGE_MODE` | `union` | `union`：FTS∪结构化∪wiki；`intersect`：FTS ∩ (结构化∪wiki)，一侧为空则回退 |
| `LAW_FINDER_PETITION_MODE` | `0` | `1`/`true`/`yes` 时并入 `LAW_FINDER_PETITION_SCOPE` 类目 |
| `LAW_FINDER_PETITION_SCOPE` | `信访` | 逗号分隔 type 片段 |

阶段耗时：`timed_stage` 含 `law_match_category_law_llm`、`law_match_find_article`（见 `perf_log`）。

