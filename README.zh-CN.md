# mirror-dialogue

把个人随笔、日记、日志、文集视为**「作者与自我、他人、时间、环境之间的镜面对话」**，以多学科视角做深度分析，最终生成一份结构化、可追溯的完整 HTML 报告。

> English docs: [README.md](README.md)

## 项目简介

`mirror-dialogue` 不是泛泛的文本分析工具，而是一个带有明确分析视角的 **Skill**：它把每一篇文本当作一面镜子，系统性地照见「作者在对谁说话、如何称呼自己、如何与自我对话、什么没说出口」。在此基础上，以 15 个学科透镜（文学 / 语言学 / 心理学 / 社会学 / 历史 / 哲学 / 宗教 / 性别 / 生态 / 医学 / 传播 / 教育 / 经济政治法律 / 艺术 / 数字人文）做路由与交叉剖析，最终合成一份「分析深度优先」的 HTML 报告。

核心设计原则：**方法论定骨架，LLM 填血肉**——脚本只做精确计算（字数、词频、引用定位、时间线、证据计数），内容判定（什么算引用、什么算核心学科、镜面对话怎么判）交给 LLM 的「标记层」，报告结构由模板统一渲染。

> 设计初衷、架构分层与市场定位见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 功能特性

- **镜面对话分析**（核心）：单篇六要素（对话对象 / 代词指认 / 自我称谓变化 / 自我对话模式 / 沉默 / 轨迹）+ 全局专章五部分（对话对象谱系 / 称谓时间线 / 对话模式 / 沉默考古 / 对话伦理）。
- **多学科透镜**：15 学科按 `when/questions/concepts` 路由为 core / secondary / excluded，核心学科深入、辅助学科补充、低相关学科在附录说明。
- **跨学科综合**：共识、分歧（含「为什么」）、互补、盲点、同一现象的多元解释（≥8 组）与综合模型。
- **情感动力学（可选）**（UED 简化版）：提供 `emotion_annotation.json` 时，逐段标注 VAD（效价 / 唤醒 / 控制），计算 Home Base、Variability、Instability、Rise/Recovery Rate 等动态指标。
- **引用分析**：判定「什么算引用」、来源猜测、功能判断（必须具体到上下文）。
- **引用与关键句分离**：`quotes` 只放判定后的引用（含位置与功能）；原文逐字但不在引号或书名号内的关键句放入 `key_sentences`，单独渲染。闸门同时校验引用清单与引用位置。
- **事前闸门**：`validate.py --gate-only` 在生成 HTML 前拦截结构完整但内容浅的报告；检查深度、证据、引用清单与位置、文献、隐私、HTML 结构。
- **隐私脱敏**：手机号 / 身份证 / 邮箱 / 座机正则 + 姓名 / 地址显式名单。
- **产物隔离**：`output/`、输入材料目录与本地知识库用户文件默认被 Git 忽略；处理真实材料时建议用 `--out` 指向仓库外目录。
- **文献核验开关**：联网时由主 agent 核验真实文献；离线时标注「未检索，需核验」，绝不编造；`knowledge_lookup.py` 记录所选模式与来源。

## 快速开始

### 环境要求

- Python 3.12+
- 依赖：`jieba`、`pyyaml`、`jinja2`、`python-docx`

### 安装

```bash
git clone https://github.com/SunshineMahiru/mirror-dialogue.git
cd mirror-dialogue
pip install -r requirements.txt
```

### 首次运行

```bash
OUT=/path/to/output
python run.py --target-dir /path/to/your/texts --out "$OUT" --config ./config.yaml
```

首次运行会把清单、统计与时间线产物写入 `$OUT`，随后因缺少 `annotation.json`
打印待办并退出。继续按下方五阶段流程操作；阶段 3 与阶段 5 必须使用同一个
`--out "$OUT"`。

## 五阶段流程

分析流程由 `run.py` 串联，分五个阶段（脚本计算与 LLM 分析交替）：

```bash
# 阶段 1：跑纯计算脚本（扫描/统计/时间线），annotation.json 缺失时打印待办并退出
OUT=/path/to/output
python run.py --target-dir "/path/to/your/texts" --out "$OUT" \
  --config ./config.yaml --knowledge-source builtin

# 阶段 2：LLM 通读原文，产出 annotation.json
#         （引用候选 + 学科路由）；可选产出 emotion_annotation.json 供 UED 指标使用
#         见 prompts/annotate.md

# 阶段 3：沿用阶段 1 产物；脚本读 annotation.json 做精确定位与证据计数
python run.py --target-dir "/path/to/your/texts" --out "$OUT" \
  --config ./config.yaml --skip-stage1

# 阶段 4：LLM 分批生成 4 个分析 JSON
#         （single / global / discipline / cross，深度门槛见 methodology/depth.md）

# 阶段 5：分析 JSON 齐全后 build；build 前自动跑事前闸门
python run.py --target-dir "/path/to/your/texts" --out "$OUT" \
  --config ./config.yaml --run-llm-check --skip-scripts
```

### `run.py` 参数

| 参数 | 作用 |
|------|------|
| `--target-dir` | 待分析的文本目录；留空时读 `config.yaml` 的 `target_dir` |
| `--out` | 产物输出目录；默认读 `config.yaml` 的 `output_dir`（`./output`） |
| `--config` | 配置文件；默认 `./config.yaml` |
| `--html` | HTML 路径；优先读 `output_html`，否则回退到 `$OUT/report.html` |
| `--disciplines` / `--template` / `--local-dir` | 可选的学科清单、HTML 模板与本地知识库目录覆盖 |
| `--skip-stage1` | 跳过阶段 1（沿用 ingest/stats/timeline 产物） |
| `--skip-scripts` | 跳过全部脚本（纯 build 模式） |
| `--run-llm-check` | 分析 JSON 齐全时继续 build_html |
| `--force` | 闸门有 fail 时仍强制渲染（页面标注「不合格草稿」） |
| `--knowledge-source` | `network` / `local` / `builtin` |

## 运行测试

```bash
python -m unittest discover tests
```

请在执行过 `pip install -r requirements.txt` 的解释器下运行；测试会直接导入脚本及其必需依赖。当前共 44 项测试。

## 目录结构

```text
mirror-dialogue/
├── SKILL.md              # 主说明书（完整工作流与硬性规则）
├── run.py                # 编排入口（五阶段）
├── validate.py           # 自检 + 事前闸门（--gate-only）
├── schema.json           # 机器可读校验 schema（深度阈值 + 要点清单）
├── config.yaml           # 停用词 / 隐私规则 / 网络开关 / 输出路径
├── requirements.txt      # 依赖清单
├── Dockerfile            # 容器镜像
├── methodology/          # 方法论层（9 个文件：README + 8 篇主题文档）
├── prompts/              # 子提示词（7 篇：标记层 / 单篇 / 全局 / 学科 / 跨学科 /
│                         #   引用 / 语义校验）
├── scripts/              # 计算脚本（8 个：ingest / stats / quotes / timeline /
│                         #   discipline_router / emotion_dynamics / knowledge_lookup /
│                         #   build_html）
├── templates/            # HTML 报告模板
├── knowledge/            # 学科定义 + 本地文献模板
├── tests/                # 单元测试（unittest）
└── .github/workflows/    # CI 与发布
```

> `output/`、输入材料目录（`input/`、`materials/`、`corpus/`、`texts/`、`sources/`）、
> `knowledge/references/` 下的本地用户文件，以及 `reference-projects/` 已被 `.gitignore` 排除，不入库。

## 配置说明

`config.yaml` 关键配置项：

| 配置 | 说明 |
|------|------|
| `supported_extensions` | 支持的文本扩展名（`.txt`、`.md`、`.docx`；旧式 `.doc` 会明确报不支持） |
| `privacy_mode` / `privacy_patterns` | 隐私脱敏开关与正则（手机号/身份证/邮箱/座机） |
| `privacy_names` / `privacy_addresses` | 姓名 / 地址显式脱敏名单 |
| `allow_network` | 是否允许联网检索学科知识 |
| `verify_references` | 文献核验开关（关联 `allow_network`；未联网自动关闭，只标「需核验」） |
| `output_dir` / `output_html` | 输出目录与最终 HTML 路径 |
| `knowledge_source` / `local_knowledge_dir` | `builtin` / `local` / `network`，以及本地文献根目录 |
| `html_template` / `disciplines_yaml` | 报告模板与学科清单路径 |
| `chunk_batch` | 单篇 Map 每批读取的篇数 |
| `min_evidence_per_core` | 每个核心学科的最低证据条数 |

深度门槛见 `schema.json`（机器可读）与 `methodology/depth.md`（人读），二者一致：**深度 ≠ 字数，要点覆盖为主、字数兜底为辅**。

## 贡献指南

欢迎提交 Issue 与 Pull Request。贡献前请注意：

1. **四层边界铁律**：方法论层定义规则 → 标记层（LLM）执行判定 → 计算层（脚本）精确计算 → 分析层（LLM）深化阐释。**脚本退回计算，判定交还 LLM**——不要在脚本里用启发式函数决定「什么算引用」「什么算核心学科」。
2. **闸门一致性**：新增质量校验时，同步更新 `schema.json`（机器可读）与 `methodology/`（人读），并补对应测试。
3. **测试**：改动后运行 `python -m unittest discover tests`，保持全绿。
4. **深度方法论**：涉及深度门槛的改动，须在 `methodology/depth.md` 统一描述，避免散落的数字冲突。
5. **隐私与伦理**：本项目用于分析真实日记，须恪守「只能描述、不能诊断」的底线，涉及强烈负面情绪时保留危机干预提示。

## 许可证

本项目采用 [MIT License](LICENSE)。
