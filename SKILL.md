---
name: mirror-dialogue
description: 分析随笔、日记、日志、文集，把每篇文本视为作者与自我、他人、时间、环境之间的“镜面对话”，并介入全面的多学科视角（文学/语言学/心理学/社会学/历史/哲学/宗教/性别/生态/医学/传播/教育/经济政治法律/艺术/数字人文），查找学科知识，生成包含字数统计、关键词频次、引用分析、主题、情感、时间线、镜面对话、多学科深度剖析与跨学科综合的完整 HTML 报告。当用户要求“分析我的日记/随笔/文集”“镜面对话分析”“多学科/各学科视角剖析随笔集”时使用。
---

# 随笔/日记镜面对话 + 多学科透镜分析师

## 目标

把每篇文本视为作者与自我、他人、时间、环境的“镜面对话”，输出可追溯、可验证、
可浏览的 HTML 深度报告，并介入全面学科视角进行证据化、可核验的多学科剖析。

## 核心分工原则（四层边界）

| 层 | 谁来做 | 做什么 |
|----|--------|--------|
| **方法论层**（`methodology/`） | 定义规则 | 定义「什么算引用 / 什么算核心学科 / 镜面对话怎么判」 |
| **标记层**（LLM） | 执行判定 | 通读原文，产出 `annotation.json`（引用候选 + 学科路由判定） |
| **计算层**（`scripts/`） | 精确计算 | 字数、词频、TF-IDF、引用定位/计数、时间线、证据命中计数 |
| **分析层**（LLM） | 深化阐释 | 镜面对话解读、主题归纳、学科剖析，基于标记层 + 计算层 |

**铁律：判定交给 LLM（标记层），脚本退回计算。** 脚本不再用启发式函数判定「什么算引用」、
「什么算核心学科」。

- **统计交给脚本**：字数、词频、TF-IDF、n-gram、共现、引用定位/计数、时间线等精确任务，
  一律由 `scripts/` 计算，不得凭感觉编造数字。
- **判定交给 LLM**：引用是否成立、学科路由、镜面对话解读、主题归纳、学科阐释，由 LLM
  依据 `methodology/` 目录的方法论完成，先产出标记层再深化。
- **HTML 交给模板**：用 `templates/report.html.j2` + `scripts/build_html.py` 渲染，保证结构一致。

## 硬性规则

1. 字数、词频、段落、引用位置必须由 `scripts/` 计算，不得凭印象写数字。
2. 每篇分析必须包含原文引用片段，标注文件名与段落号。
3. 推断必须标注“推断”，证据不足标注“证据不足”。
4. 最终报告写入 HTML 文件；聊天中只返回摘要、统计概览和文件路径。
5. 默认本地处理；如需展示，先做隐私脱敏。
6. 学科知识必须真实可追溯；无法核验时标注“未检索，需核验”，不得编造文献、理论、引文。
7. 禁止临床诊断、病理化、道德审判。心理学/医学分析只能描述，不能下诊断。
8. 先做“学科路由”，不是所有学科平均用力；核心学科深入，辅助学科补充，低相关学科不强行分析。
9. 报告总长不设上限，但必须分块生成、分批写入，避免模型输出截断。
10. 报告主体必须是分析，不是统计。统计表（字数/词频/引用表）一律移入附录，正文只放分析结论。
11. 每篇分析的"读者感受"优先级：分析深度 > 结构完整 > 数据密度。宁可少一张表，不可少一段论证。
12. 判定标准：如果一份报告把"统计表格"和"分析正文"的字数比超过 1:2，视为不合格。
13. 禁止用固定模板套话（"以XX为核心""体现XX主旨""深化了XX主题"）。每一篇判断必须有该篇独有的具体内容，落到具体句子、具体段落、具体意象。
14. 引用的"功能判断"必须具体到该引用的上下文，不能笼统说"起到抒情作用""增强感染力"。必须说明：这条引用在此处为何是抒情而非佐证、它回应了前文的哪一处、改变了什么情绪走向。

## 输入参数

| 参数 | 含义 | 默认 |
|------|------|------|
| `{{TARGET_DIR}}` | 待分析目录 | 必填 |
| `{{OUTPUT_HTML}}` | 输出 HTML 路径 | `./output/report.html` |
| `{{PRIVACY_MODE}}` | 是否脱敏 | 是 |
| `{{ALLOW_NETWORK}}` | 是否联网检索 | 否 |
| `{{KNOWLEDGE_SOURCE}}` | 学科知识来源 | builtin |

## 工作流

严格按以下顺序执行，每一步的产物作为下一步输入。

### 编排入口（推荐）

四层分工由 `run.py` 串联，流程分五阶段：

```bash
# 阶段1：跑纯计算脚本（ingest/stats/timeline）；annotation.json 缺失时脚本打印待办并退出
python run.py --target-dir "{{TARGET_DIR}}" --out ./output \
  --config ./config.yaml --knowledge-source builtin

# 阶段2：agent 通读原文，按 prompts/annotate.md 产出标记层 annotation.json
#        （quotes[] 引用候选 + discipline_plan 学科路由判定）

# 阶段3：重跑（跳过阶段1），脚本读 annotation.json 做精确定位/证据计数，然后检查分析 JSON
python run.py --target-dir "{{TARGET_DIR}}" --skip-stage1

# 阶段4：agent 分批生成 4 个分析 JSON（单篇 Map / 全局 Reduce / 逐学科 / 跨学科）

# 阶段5：分析 JSON 齐全后重跑（纯 build 模式）；build 前自动跑事前闸门（validate.py）
python run.py --target-dir "{{TARGET_DIR}}" --run-llm-check --skip-scripts
```

`run.py` 阶段说明：

| 阶段 | 内容 | 谁做 |
|------|------|------|
| 1 | ingest → stats → timeline（纯计算） | 脚本 |
| 2 | annotation.json（标记层：引用候选 + 学科路由判定） | LLM |
| 3 | quotes（定位/计数）→ discipline_router（证据命中计数）→ knowledge_lookup | 脚本 |
| 4 | single / global / discipline / cross 四个分析 JSON | LLM |
| 5 | build_html（build 前自动跑事前闸门） | 脚本 |

- 不带 `--skip-*`：跑阶段 1（ingest/stats/timeline），检查 `annotation.json`；缺失则打印待办退出，
  存在则继续阶段 3（quotes/discipline_router/knowledge_lookup）。
- `--skip-stage1`：只跳过阶段 1（沿用 ingest/stats/timeline），仍跑阶段 3（读 annotation）。
- `--skip-scripts`：跳过全部脚本（阶段 1+3），沿用已有产物，只检查分析 JSON 并 build（纯 build 模式）。
- **事前闸门（P0）**：build 前强制跑 `validate.py --gate-only`（内容检查，跳过 HTML），
  fail 非空默认拒绝渲染，把 fail 清单输出为待办；追加 `--force` 可强制渲染
  「不合格草稿」（页面顶部标红）。build 后自动跑完整 validate（含 HTML 结构）。

不强制使用 `run.py`；也可按下方各步骤手动调用单个脚本，但必须保证顺序与产物一致。

### 第一步：扫描与解析

调用 `scripts/ingest.py`，扫描 `{{TARGET_DIR}}` 下所有 `.txt/.md/.doc/.docx`，
做编码识别、frontmatter/HTML 标签/页码/重复空行清洗、隐私脱敏，输出 `files_manifest.json`。

```bash
python scripts/ingest.py --target-dir "{{TARGET_DIR}}" --out ./output --config ./config.yaml
```

校验：确认 `files_manifest.json` 覆盖目录中所有文本文件，不能漏文件。

### 第二步：脚本统计（纯计算）

产出统计 JSON（不依赖标记层）：

```bash
python scripts/stats.py --manifest ./output/files_manifest.json --out ./output --config ./config.yaml
python scripts/timeline.py --manifest ./output/files_manifest.json --out ./output
```

产物：`stats.json`（基础统计）、`keywords.json`（词频+TF-IDF）、`ngrams.json`、
`cooccurrence.json`、`timeline.json`（日期/情感曲线）。

### 第三步：标记层（LLM，判定交给 LLM 的落地）

通读原文，按 `prompts/annotate.md` 产出 `annotation.json`，含：

- `quotes[]`：判定「什么算引用」（含来源猜测、功能、判定依据、一句话解读）。
- `emphasis_quotes[]`：强调/专名引号（不计入引用总数）。
- `discipline_plan`：判定学科路由（core/secondary/excluded + 判定依据 + 证据信号）。

判定规则见 `methodology/quote-analysis.md` 与 `methodology/discipline-routing.md`。

### 第四步：引用定位 + 学科证据计数（脚本，读标记层）

脚本读 `annotation.json`，**只做精确计算，不再自行判定**：

```bash
python scripts/quotes.py --manifest ./output/files_manifest.json \
  --out ./output --config ./config.yaml --annotation ./output/annotation.json

python scripts/discipline_router.py \
  --manifest ./output/files_manifest.json \
  --stats ./output/stats.json --keywords ./output/keywords.json \
  --quotes ./output/quotes.json --timeline ./output/timeline.json \
  --disciplines ./knowledge/disciplines.yaml --out ./output \
  --annotation ./output/annotation.json
```

- `quotes.py`：对标记层的引用候选做精确定位（段落号）、计数、密度、来源分布。
- `discipline_router.py`：对每个学科做证据命中计数（供 LLM 参考）；core/secondary 判定
  来自 `annotation.json`，**不再用 `avg*1.2` 一刀切**。数字人文始终 core。
- 产出 `quotes.json`、`discipline_plan.json`（含 `hit_counts` 与 `method` 标注）。

### 第五步：单篇 Map

每次读取 3-5 篇，使用 `prompts/map_single.md`，对每篇输出 `single_analysis.json`。

字段：`file, title, date_guess, stats, summary, themes, style, emotion,
emotion_turning_points, mirror_dialogue, keywords, quotes, quote_analysis,
evidence, uncertainty`。

每篇必须包含：基础统计、核心主题、语言风格、情感基调与转折、镜面对话、关键词、
引用分析、至少 8 条原文引用片段（每条有 interpretation，标注文件与段落号）。
深度硬门槛（见 `methodology/depth.md`，深度≠字数、要点覆盖为主）：summary ≥ 1200 中文字符、
mirror_dialogue ≥ 500 字兜底 + 六要素全覆盖、quote_analysis ≥ 300 字、
emotion_turning_points ≥ 300 字。

### 第六步：逐学科分析

- 对每个**核心学科**，使用 `prompts/discipline_analysis.md`，输出 `discipline_analysis.json`。
- 对辅助学科，可合并为简短分析。
- 调用 `scripts/knowledge_lookup.py` 记录每个概念的学科知识来源，输出 `knowledge_sources.json`。

每个核心学科必须按以下结构输出（八要素缺一不可）：
1) 核心问题 2) 关键概念/理论 3) 方法（≥200 字）4) 原文证据（至少 3 条，标注文件与段落）
5) 解释 analysis（≥1500 字）6) 反证 counter_evidence（≥300 字，须与 analysis 对话）
7) 置信度 8) 学科知识来源（作者、书名/论文、年份、页码/URL）。

### 第七步：跨学科综合

使用 `prompts/cross_discipline.md`，输入所有 `discipline_analysis.json`、
`global_analysis.json`、`quotes.json`、`timeline.json`，输出 `cross_discipline.json`。

包含：共识、分歧、互补、盲点、同一现象多元解释、跨学科综合模型、进一步研究问题、局限与伦理。

### 第八步：全局 Reduce

使用 `prompts/reduce_global.md`，汇总所有 `single_analysis.json` 与统计 JSON，
输出 `global_analysis.json`。

必须包含：文件总览、总字数/总段落/时间范围/写作频率、高频词表、TF-IDF 表、n-gram、
共现、引用总表、情感曲线、时间线、主题聚类（按语义层分组）、篇间关联（谱系判断）、
镜面对话专章（mirror_dialogue_chapter，≥1500 字）、整体编排逻辑（结构判断）、
≥15 条重要发现（每条有证据）、局限与不确定性。

### 第九步：生成 HTML（build 前自动跑事前闸门）

```bash
python scripts/build_html.py --data-dir ./output --out "{{OUTPUT_HTML}}" \
  --template ./templates/report.html.j2
```

> 推荐用 `run.py --run-llm-check` 而非直接调 build_html：它会**在 build 前强制跑
> `validate.py --gate-only`**（内容闸门）。fail 非空默认拒绝渲染、输出 fail 清单；
> 追加 `--force` 可强制渲染「不合格草稿」。

渲染后校验：目录锚点可跳转、表格数据、引用位置、图表数据是否与 JSON 一致。

### 第十步：自检

```bash
python validate.py --data-dir ./output --config ./config.yaml
# --manifest 可省略：默认自动读 ./output/files_manifest.json
# --html 可省略：默认校验 ./output/report.html；自定义 HTML 路径时显式传入
# python validate.py --data-dir ./output --html ./output/final.html
```

输出 `validation_report.json`，脚本化校验：schema 字段对齐（含 knowledge_sources.json）、
文件覆盖、引用可定位、学科证据数量、文献核验状态（核心学科 references 全未核验 → fail）、
隐私脱敏（对比原始文件与脱敏后 content）、降级模式标注、跨学科综合完整性、HTML 结构
（章节锚点/表格/blockquote/折叠数量）。**另含四项深度/对齐闸门（本次补齐）：**

- **镜面对话专章**：`mirror_dialogue_chapter` 五部分齐全且 ≥1500 字（字段名必须对齐，
  误写 `mirror_dialogue_overview` 会被拦截）。
- **单篇镜面对话字段**：`pronoun_map` / `self_naming_change` 等字段必须存在。
- **跨学科多元解释**：`multi_explanations` ≥8 组、`synthesis_model`、`complementary`、
  `limitations_ethics` 必须存在。
- **统计:分析字数比**：附录（stats/keywords/quotes/references）与分析正文
  （per-file/discipline-analysis/mirror-dialogue）字数比 ≤1:2。

若 fail 非空，须修复后重跑。运行测试：`python -m unittest discover tests`。

> 约束：`files_manifest.json` 的 `file` 字段必须为**绝对路径**（ingest.py 默认如此），
> 否则 validate.py 的隐私检查会因读不到原始文件而记 warn（不静默跳过）。

## 分块生成机制（防 token 截断）

1. **单篇 Map 分块**：每次只读 3-5 篇原文（`config.yaml` 的 `chunk_batch`），逐篇产出
   `single_analysis.json` 条目后追加合并，避免一次塞入全部原文撑爆上下文。
   - `chunk_batch` 的消费者是**执行分析的 agent**：SKILL.md 第三步要求 agent 按此值
     分批读取原文，脚本不参与此分块（脚本只做统计，不做 LLM 分析）。
2. **逐学科分块**：按 `discipline_plan.json` 的 core 学科逐个调用 `discipline_analysis.md`，
   一个学科一个 JSON 条目，不要一次性输出全部学科。
3. **HTML 写入**：`build_html.py` 由 Python 一次性渲染完整文件，脚本不受 token 限制，
   因此 HTML 阶段无需分块；分块只针对 LLM 生成分析 JSON 的阶段。

> 补充：`run.py` 第二次运行应加 `--skip-scripts`，避免从 ingest 开始全量重算（见下）。

## 镜面对话分析要点

这是本 Skill 的**核心诉求**，不能省略。

### 单篇层面（`map_single.md`，`mirror_dialogue` ≥500 字兜底 + 六要素全覆盖）

每篇必须逐项回答：
- 作者在对谁说话（过去的我/未来的我/某人/上帝/命运/读者/物品/城市/抽象概念）；
- “你/他/她/我们”各指谁，给出至少 3 处原文例证；
- 自我称谓如何变化（我/自己/本人/俺/笔者/你自称/我们），至少 3 处变化实例；
- 自我审判、自我安抚、自我追问、自我鼓励如何交替，四种各至少 1 处具体场景；
- 有哪些未说出口的话（沉默分析：省略号、破折号、断裂句、回避话题）；
- 对话对象的移动轨迹（从谁开始，到谁结束）。

### 全局镜面对话专章（`reduce_global.md`，`mirror_dialogue_chapter` ≥1500 字）

在 HTML 报告新增独立章节 `#mirror-dialogue`，位置在逐篇分析之后、多学科分析之前，
包含五部分（缺一不可）：
1. **对话对象谱系**：所有对话对象按出现频次和情感强度排序，附证据。
2. **自我称谓变化时间线**：按文件顺序，展示“我→我们→他（客体化）”的演化。
3. **三种自我对话模式（审判/安抚/追问）的分布与交替规律**。
4. **未说出口的话（沉默考古）**：从省略号、破折号、断裂句、回避话题中提炼。
5. **对话伦理**：作者如何对待“他者”作为对话者。

## 分析维度补充

时间（日/周/月/年写作量、季节、深夜/清晨倾向）、人物（人名/称谓/关系/共同出现网络）、
空间（地点/房间/城市/天气/光线/声音）、身体（睡眠/饮食/疼痛/疲惫/呼吸/心跳）、
情绪（焦虑/愤怒/平静/羞耻/希望/孤独/感激）、自我指涉（我/自己/本人/俺/笔者/你/我们）、
重复母题（意象/句子/梦/书/歌/路/窗/雨）、引用功能（佐证/抒情/反讽/共鸣/逃避/权威/对话/装饰）、
篇章逻辑（时间线/主题线/情绪线/空间线/人物线）。

## 知识查找规则

知识来源分三档，真实性等级递减，报告中必须如实标注：

1. **联网检索（最高）**：优先查权威教材、综述、百科、论文摘要；记录作者、标题、年份、
   页码或 URL、访问日期；不得把搜索摘要当原文引用。
2. **本地知识库（次高）**：用 `scripts/knowledge_lookup.py` 检索 `knowledge/references/`，
   输出命中文件与片段作为可追溯来源。
   - 本地库默认只有 `README.md`，**没有真实文献**。本地库未命中时，来源须降级标注
     “未检索，需核验”，不得假装命中。
   - 用户如需真实知识库，按 `knowledge/references/REFERENCES_TEMPLATE.md` 录入文献后再跑。
3. **内置知识（最低）**：`knowledge_lookup.py --source builtin` 会给每条概念标记
   "模型内部知识，未检索，需核验"。此时文献条目一律不写具体页码，且必须在报告里
   显著提示"学科知识未经外部核验"。

### 文献核验开关（`verify_references`）

`config.yaml` 的 `verify_references` 默认开启，且**关联 `allow_network`**：

- 联网（`allow_network: true`）→ 核验真实文献，核心学科 references 全未核验判 fail。
- 未联网（`allow_network: false`）→ 核验**自动关闭**：不使用外部文献、只标
  「未检索，需核验」、绝不编造；此时 `validate.py` 不把「未核验」判为编造红线 fail
  （诚实标注不算编造）。

通用红线：

- **禁止编造**：不虚构作者、书名、年份、理论；不把网络流行语当学术概念。
- **禁止把“模型记忆”当“已检索”**：未联网/未命中本地库的，一律标“需核验”。
- **区分三类内容**：原文证据、学科知识、分析者推断，报告中必须可区分。

## 引用抽取规则

- 直接引用模式：中文引号“”（6-200 字）、英文引号""（6-200 字）、书名号《》、篇名号〈〉。
- 引述动词：说、写道、提到、引用、如、所谓、记得、有人说、书上说、曾言、尝云。
- **引用判定**（满足其一才计入引用总数）：
  1. 引述动词在引号前 20 字内出现；
  2. 书名号《》或篇名号〈〉包裹；
  3. 引号内容 ≥ 15 字且含完整主谓结构。
- 不满足的引号内容归入 `emphasis_quotes`（强调/专名），**不计入引用总数**。
- `source_guess` 只看引号前 50 字上下文，不看引用文本自身。
- 来源分类：自引/他人/书/文章/歌词/电影/网络/不明；不明就写“不明”，不得虚构。
- 输出字段：引用文本 | 来源猜测 | 文件 | 位置 | 功能 | 前后情绪 | 解释 | 置信度。

## 质量校验清单

完成报告后，逐项自检：

- [ ] 目录中所有文本文件都已覆盖。
- [ ] 字数、段落、词频来自脚本，不是模型估算。
- [ ] 每篇至少 8 条原文引用，每条有 interpretation，可搜索定位。
- [ ] 每篇 summary ≥ 1200 中文字符；mirror_dialogue ≥ 500 字兜底 + 六要素全覆盖。
- [ ] 引用来源不明时标注“不明”，不编造。
- [ ] 推断处标注“推断”，证据不足处标注“证据不足”。
- [ ] 隐私信息已脱敏。
- [ ] HTML 可直接打开，目录锚点正确。
- [ ] 报告主体是分析，统计表在附录，统计与分析字数比 ≤ 1:2。
- [ ] HTML 含镜面对话专章 `#mirror-dialogue`（五部分齐全，≥1500 字）。
- [ ] 表格、图表数据与 JSON 一致。
- [ ] 长报告分块生成，未因 token 截断。
- [ ] 是否先做学科路由，而非所有学科平均用力。
- [ ] 核心学科是否至少 3 条原文证据。
- [ ] 每个学科八要素（问题/概念/方法/证据/解释/反证/置信度/文献）齐全且全部渲染；
      analysis ≥ 1500 字、counter_evidence ≥ 300 字、methods ≥ 200 字。
- [ ] 全局重要发现 ≥ 15 条，每条附证据。
- [ ] 学科知识来源是否可追溯；未检索的是否标注“需核验”。
- [ ] 是否没有编造文献、理论、引文。
- [ ] 是否没有临床诊断、病理化、道德审判。
- [ ] 是否呈现学科间分歧与互补，且解释“为什么分歧”。
- [ ] 是否给出同一现象的多元解释 ≥ 8 组。
- [ ] HTML 是否包含多学科章节、跨学科综合、参考文献。
- [ ] 聊天是否只返回路径、摘要和关键发现。

## 聊天回复格式

完成分析后，聊天中只返回：
- 文件路径
- 总文件数、总字数、时间范围
- Top 20 关键词
- 引用数量
- 启用学科列表
- 3-5 条最重要发现

不要把最终 HTML 全文塞进聊天回复。

## 资源清单

| 路径 | 用途 |
|------|------|
| `run.py` | 编排入口，五阶段串联（纯计算 → 标记层 → 定位计数 → 分析 → build+闸门） |
| `validate.py` | 自检脚本：schema 对齐 + 质量清单 + **事前闸门（`--gate-only`）** |
| `schema.json` | 机器可读校验 schema（深度阈值 + 要点清单的单一事实源） |
| `methodology/` | 方法论层：mirror-dialogue / text-analysis / quote-analysis / discipline-routing / report-structure / depth / emotion-dynamics / knowledge-rules |
| `scripts/ingest.py` | 扫描解析清洗脱敏，产出 files_manifest.json |
| `scripts/stats.py` | 字数/段落/句子/词频/TF-IDF/n-gram/共现（含降级标注） |
| `scripts/quotes.py` | 读标记层做引用定位/计数/密度（不再自行判定「什么算引用」） |
| `scripts/timeline.py` | 日期识别、时间线、情感曲线（含方法标注）、时间槽/季节 |
| `scripts/discipline_router.py` | 读标记层做学科证据命中计数（core/secondary 判定来自 annotation） |
| `scripts/emotion_dynamics.py` | UED 情感动力学指标计算（读 VAD 标注算 6 指标） |
| `scripts/knowledge_lookup.py` | 学科知识检索与来源记录 |
| `scripts/build_html.py` | Jinja2 渲染 HTML + 校验（支持 `--force` 草稿标注） |
| `templates/report.html.j2` | HTML 报告模板（含降级/方法/校验状态/草稿横幅） |
| `prompts/annotate.md` | 标记层子提示词（引用候选 + 学科路由判定 + 情感 VAD 标注） |
| `prompts/verify.md` | 语义校验子提示词（fact-checker + red-team） |
| `prompts/map_single.md` | 单篇分析子提示词 |
| `prompts/reduce_global.md` | 全局综合子提示词 |
| `prompts/quote_analysis.md` | 引用专项子提示词 |
| `prompts/discipline_analysis.md` | 单学科分析子提示词 |
| `prompts/cross_discipline.md` | 跨学科综合子提示词 |
| `knowledge/disciplines.yaml` | 15 个学科透镜定义 |
| `knowledge/references/` | 本地学科知识库（默认空，需用户录入真实文献） |
| `config.yaml` | 停用词、隐私规则、输出路径、图表开关、`verify_references` 核验开关等 |
| `requirements.txt` | 依赖清单（jieba/pyyaml/jinja2） |
| `.github/workflows/ci.yml` | CI：跑单测 + 语法检查 |
| `tests/` | 单元测试（unittest，`python -m unittest discover tests`） |

## 依赖

- Python 3：`jieba`（分词）、`PyYAML`（配置/学科清单）、`jinja2`（HTML 渲染）。
- 可选：`python-docx`（解析 .docx）。
- 安装：`pip install jieba pyyaml jinja2 python-docx`

缺失依赖时脚本会降级运行，并在 `stats.json` 里标注 `method.degraded=true`，
HTML 报告基础统计章节会显式提示“降级模式”：

- 无 jieba：词频/TF-IDF/n-gram/共现退化为按字切分，多字词统计精度下降。
- 无 python-docx：`.docx` 无法解析，`files_manifest.json` 中该文件记录读取失败错误。

降级不影响字数/段落/句子等基础统计（不依赖分词），但关键词类指标须以标注为准，
不得把降级结果当作精确词频呈现。
