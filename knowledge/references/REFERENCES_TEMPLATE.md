# 本地学科文献录入模板

> 本目录默认不含任何真实文献。`knowledge_lookup.py` 在 `local` 模式下按概念关键词
> 检索本目录文件名与内容；未命中时来源会降级标注「未检索，需核验」。

## 为什么要录入真实文献

内置知识模式（`builtin`）下，LLM 输出的概念/理论来源是模型记忆，**可能编造或记错
作者、书名、年份、页码**。为了让「文献可追溯」真正成立，需要用户把自己确认过的
真实文献放入本目录，并把 `config.yaml` 的 `knowledge_source` 改为 `local`。

## 录入方式

每个概念/理论一条记录，文件名建议含概念或作者，例如 `psychology/attachment-bowlby.md`。
内容采用下列固定字段，便于检索与报告中引用：

```markdown
---
discipline: psychology
concept: 依恋理论
author: John Bowlby
title: Attachment and Loss, Vol.1: Attachment
year: 1969
publisher: Basic Books
page: 194
url: ""
verified: true
---

[此处写该理论的一句话摘要，供分析时引用]
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| discipline | 是 | 对应 `disciplines.yaml` 的学科 id |
| concept | 是 | 概念/理论名，用于检索匹配 |
| author | 是 | 作者（真实姓名） |
| title | 是 | 书名/论文题名（真实） |
| year | 是 | 出版/发表年份 |
| publisher | 否 | 出版社/期刊 |
| page | 否 | 具体页码（确认过才填，否则留空） |
| url | 否 | 可访问链接 |
| verified | 是 | `true` 表示人工核验过，`false` 表示待核验 |

## 红线

1. **只录入你确认真实存在的文献**。不要为了让报告好看而填“看起来像真的”条目。
2. 页码不确定就留空，报告中会显示为“未检索，需核验”，绝不编造页码。
3. 每条记录 `verified: false` 的，报告参考文献会标注核验状态，不得当作已核验引用。
4. 录入后跑 `python validate.py` 会检查学科分析的 `references.verified` 是否与本地库一致。
