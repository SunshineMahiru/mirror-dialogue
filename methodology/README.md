# methodology/ — 方法论层（唯一权威载体）

## 定位

本目录是「怎么做分析」的**唯一权威说明**，把原先散落在 `SKILL.md`、`prompts/`、
`scripts/` 注释里的判定规则收敛到一处，供 LLM 在执行「标记层」与「分析层」时完整读取。

这是本 Skill 架构的核心原则落地：

| 层 | 谁来做 | 做什么 |
|----|--------|--------|
| **方法论层**（本目录） | 定义规则 | 定义「什么算引用 / 什么算核心学科 / 镜面对话怎么判」 |
| **标记层**（LLM） | 执行判定 | 通读原文，按本目录规则产出 `annotation.json` 标记 |
| **计算层**（脚本） | 精确计算 | 只做定位、计数、密度、词频等确定性计算，**不做内容判定** |
| **分析层**（LLM） | 深化阐释 | 基于标记层 + 计算层的精确数据，产出分析 JSON |

**铁律：脚本退回计算，判定交还 LLM。** 脚本不再用启发式函数决定「什么算引用」、
「什么算核心学科」；这些判定由 LLM 依据本目录的方法论产出，脚本只对标记结果做精确定位与计数。

## 目录清单

| 文件 | 内容 |
|------|------|
| `mirror-dialogue.md` | 镜面对话方法论（本 Skill 核心诉求） |
| `text-analysis.md` | 文本分析方法论（风格 / 情感 / 主题 / 多维分析） |
| `quote-analysis.md` | 引用分析方法论（判定 / 来源 / 功能） |
| `discipline-routing.md` | 学科路由方法论（core / secondary / excluded 判定） |
| `report-structure.md` | 报告结构方法论（章节权重 / 正文与附录边界） |
| `depth.md` | 深度方法论（深度≠字数，要点覆盖为主 + 字数兜底） |
| `knowledge-rules.md` | 知识查找与文献红线（三档来源 / 核验开关） |

## 使用方式

1. **标记层**：LLM 通读原文，按 `quote-analysis.md`、`discipline-routing.md`、
   `mirror-dialogue.md` 的判定规则，产出 `annotation.json`（标记：引用候选、情感转折、
   学科信号、对话对象等）。
2. **计算层**：`scripts/quotes.py`、`scripts/discipline_router.py` 等脚本读取
   `annotation.json`，只做精确定位、计数、密度，不再自行判定。
3. **分析层**：LLM 基于标记层 + 计算层的精确数据，按 `text-analysis.md`、
   `report-structure.md` 深化，产出 4 个分析 JSON。

> 深度门槛（summary ≥1200、mirror_dialogue ≥800、analysis ≥1500 等）是**硬约束**，
> 由 `validate.py` 事前闸门拦截，见各方法论文件内的「深度门槛」小节。
