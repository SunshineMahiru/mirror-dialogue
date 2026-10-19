# 报告结构方法论

> 定义「报告怎么组织、正文与附录的边界、章节权重」。

## 一、章节权重（最重要）

报告主体必须是**分析**，不是统计。优先级：**分析深度 > 结构完整 > 数据密度**。
宁可少一张表，不可少一段论证。

**单篇 vs 全局的权重**：单篇深度分析（`#per-file`）为主，全局视角（镜面对话专章、
跨文件谱系）兜底。两者不冲突——单篇把每篇讲透，全局把"单篇看不到的跨篇演化"补上；
不得用全局概述替代单篇深度。

正文顺序（严格）：

1. **摘要**（`#summary`）：文件定位与关系 + 核心统计概览卡片。
2. **逐篇深度分析**（`#per-file`）：主体。每篇完整呈现 summary、风格、情感转折、
   镜面对话、引用分析、原文引用。
3. **镜面对话专章**（`#mirror-dialogue`）：独立章节，渲染五部分（见
   `mirror-dialogue.md`）。
4. **多学科深度剖析**（`#discipline-analysis`）：主体。每个核心学科独立展开，八要素
   （core_questions/concepts/methods/evidence/analysis/counter_evidence/confidence/
   references）**全部渲染**。
5. **跨学科综合**（`#cross-discipline`）：共识、分歧（含「为什么」）、互补、盲点、
   多元解释（≥8 组）、综合模型。
6. **全局综合**（`#global`）：语义层主题聚类、情感曲线、编排逻辑（结构判断）、
   谱系判断、重要发现（≥15 条）。
7. **结语与总评**（`#conclusion`）。

—— 以下移入**附录** ——

8. 基础统计（`#stats`） / 9. 关键词词频（`#keywords`） / 10. 引用分析（`#quotes`） /
11. 参考文献（`#references`） / 12. 方法、隐私、不确定性（`#appendix`）。

## 二、正文 vs 附录边界（硬性规则）

- 统计表（字数/词频/引用表）**一律移入附录**，正文只放分析结论。
- **统计与分析字数比 ≤ 1:2**，超过即不合格。
- 报告总长不设上限，但必须分块生成、分批写入。

## 三、措辞红线

- 禁止模板套话（「以 XX 为核心」「体现 XX 主旨」「深化 XX 主题」）。每一篇判断必须落到
  该篇独有的具体句子、段落、意象。
- 推断标「推断」，证据不足标「证据不足」。

## 四、技术约束

- 目录锚点可跳转；引用片段用 `<blockquote>` 并标来源；图表内联 SVG（离线）。
- 页面底部标注生成时间、分析者、校验状态。

## 五、深度门槛汇总（validate.py 闸门拦截）

- 单篇 summary ≥1200 字、mirror_dialogue 展开 ≥800 字、quotes ≥8 条（每条有解读）、
  quote_analysis ≥300 字、emotion_turning_points ≥300 字。
- 学科 analysis ≥1500 字、counter_evidence ≥300 字、methods ≥200 字。
- 全局 key_findings ≥15 条（validate 最低红线 10 条）。
- HTML 必须含 12 个章节锚点（summary/per-file/mirror-dialogue/discipline-analysis/
  cross-discipline/global/conclusion/stats/keywords/quotes/references/appendix）。
