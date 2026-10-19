# 学科路由方法论

> 定义「如何判定 core / secondary / excluded」。
> **判定交给 LLM（标记层）**，脚本只做「证据命中计数」供 LLM 参考。

## 一、判定标准

- **core（核心）**：文本实质触及该学科的核心问题，有足够原文证据支撑深入分析。
- **secondary（辅助）**：文本有所触及，但不足以支撑单独深入分析，可合并简述。
- **excluded（低相关）**：文本几乎不触及，**不强行分析**。

**核心原则：先路由，不平均用力。** 核心学科深入、辅助学科补充、低相关学科跳过。

## 二、判定依据（读 `knowledge/disciplines.yaml`）

对每个学科，LLM 读它的三个字段作判定：

1. `when`（触发条件）：文本是否触及这些主题/信号。
2. `questions`（核心问题）：这些问题对本文本是否成立、是否有答案线索。
3. `concepts`（关键概念）：这些概念是否在文本中有对应现象。

> 例：`linguistics` 的 `when` 是「人称、时态、句长、标点、词频」，这些恰是镜面对话
> 方法论的核心信号。过去脚本按关键词计数，把 `linguistics` 判成 2 分落 secondary，
> 而 `ecology_space`（触发词「自然、家、房间」）却以 60.5 分进 core——这是**关键词计数
> 误判**，已由 LLM 判定修正。

## 三、脚本职责边界

`scripts/discipline_router.py` 只做：读取标记层的学科信号 → 对每个学科的 `when` /
`concepts` 做**证据命中计数**（命中几次、命中哪些词）→ 输出 `discipline_evidence.json`
供 LLM 参考。**不再用 `avg * 1.2` 一刀切判定 core/secondary/excluded**。

## 四、特殊规则

- **数字人文（`digital_humanities`）始终作为 core**（统计基础学科）。
- 每个 core 学科至少 3 条原文证据（`min_evidence_per_core`）。

## 五、输出

`discipline_plan.json` 由 LLM 产出，字段：`core_disciplines / secondary_disciplines /
excluded_disciplines / reasons / evidence`，`reasons` 必须写明判定依据（哪条 `when` 触发、
哪个 `question` 成立）。

## 六、excluded 学科的呈现规则

「路由 + 说明」原则：core 深入、secondary 简短、**excluded 不强行分析，但必须在 HTML
附录列明「未启用及原因」**（一句话即可，如「语言学：人称/时态信号不足，未启用」）。
这样既遵守「不平均用力」，又不让「全面多学科」的承诺落空。
