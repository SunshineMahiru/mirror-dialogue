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
- **情感动力学**（UED 简化版）：逐段标注 VAD（效价 / 唤醒 / 控制），计算 Home Base、Variability、Instability、Rise/Recovery Rate 等动态指标。
- **引用分析**：判定「什么算引用」、来源猜测、功能判断（必须具体到上下文）。
- **事前闸门**：`validate.py --gate-only` 在生成 HTML 前强制拦截「结构完整但内容浅」的报告，深度不达标默认拒绝渲染。
- **隐私脱敏**：手机号 / 身份证 / 邮箱 / 座机正则 + 姓名 / 地址显式名单。
- **文献核验开关**：联网核验真实文献；未联网则诚实标注「未检索，需核验」，绝不编造。

## 安装与使用

### 环境要求

- Python 3.12+
- 依赖：`jieba`、`pyyaml`、`jinja2`

### 安装

```bash
git clone https://github.com/SunshineMahiru/mirror-dialogue.git
cd mirror-dialogue
pip install -r requirements.txt
```

### 使用（五阶段流程）

分析流程由 `run.py` 串联，分五个阶段（脚本计算与 LLM 分析交替）：

```bash
# 阶段 1：跑纯计算脚本（扫描/统计/时间线），annotation.json 缺失时打印待办并退出
python run.py --target-dir "/path/to/你的文本目录" --out ./output \
  --config ./config.yaml --knowledge-source builtin

# 阶段 2：LLM 通读原文，按 prompts/annotate.md 产出标记层 annotation.json
#         （引用候选 + 学科路由判定 + 情感 VAD 标注）

# 阶段 3：重跑（跳过阶段 1），脚本读 annotation.json 做精确定位与证据计数
python run.py --target-dir "/path/to/你的文本目录" --skip-stage1

# 阶段 4：LLM 分批生成 4 个分析 JSON
#         （single / global / discipline / cross，深度门槛见 methodology/depth.md）

# 阶段 5：分析 JSON 齐全后重跑；build 前自动跑事前闸门
python run.py --target-dir "/path/to/你的文本目录" --run-llm-check --skip-scripts
```

`run.py` 参数说明：

| 参数 | 作用 |
|------|------|
| `--target-dir` | 待分析的文本目录（必填） |
| `--out` | 产物输出目录，默认 `./output` |
| `--config` | 配置文件，默认 `./config.yaml` |
| `--skip-stage1` | 跳过阶段 1（沿用 ingest/stats/timeline 产物） |
| `--skip-scripts` | 跳过全部脚本（纯 build 模式） |
| `--run-llm-check` | 分析 JSON 齐全时继续 build_html |
| `--force` | 闸门有 fail 时仍强制渲染（页面标注「不合格草稿」） |
| `--knowledge-source` | `network` / `local` / `builtin` |

### 运行测试

```bash
python -m unittest discover tests
```

## 目录结构

```
mirror-dialogue/
├── SKILL.md              # 主说明书（完整工作流与硬性规则）
├── run.py                # 编排入口（五阶段）
├── validate.py           # 自检 + 事前闸门（--gate-only）
├── schema.json           # 机器可读校验 schema（深度阈值 + 要点清单）
├── config.yaml           # 停用词 / 隐私规则 / 网络开关 / 输出路径
├── requirements.txt      # 依赖清单
├── methodology/          # 方法论层（9 篇：镜面对话 / 文本分析 / 引用分析 /
│                         #   学科路由 / 报告结构 / 深度 / 情感动力学 / 知识规则）
├── prompts/              # 子提示词（7 篇：标记层 / 单篇 / 全局 / 学科 / 跨学科 /
│                         #   引用 / 语义校验）
├── scripts/              # 计算脚本（8 个：ingest / stats / quotes / timeline /
│                         #   discipline_router / emotion_dynamics / knowledge_lookup /
│                         #   build_html）
├── templates/            # HTML 报告模板
├── knowledge/            # 学科定义 + 本地文献模板
├── tests/                # 单元测试（unittest）
└── .github/workflows/    # CI
```

> `output/`（分析产物）与 `reference-projects/`（第三方参考源码）已被 `.gitignore` 排除，不入库。

## 配置说明

`config.yaml` 关键配置项：

| 配置 | 说明 |
|------|------|
| `supported_extensions` | 支持的文本扩展名（`.txt/.md/.doc/.docx`） |
| `privacy_mode` / `privacy_patterns` | 隐私脱敏开关与正则（手机号/身份证/邮箱/座机） |
| `privacy_names` / `privacy_addresses` | 姓名 / 地址显式脱敏名单 |
| `allow_network` | 是否允许联网检索学科知识 |
| `verify_references` | 文献核验开关（关联 `allow_network`；未联网自动关闭，只标「需核验」） |
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
