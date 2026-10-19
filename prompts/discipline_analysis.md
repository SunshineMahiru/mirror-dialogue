# 单学科分析子提示词

请从【{{DISCIPLINE_NAME}}】视角分析以下随笔/日记文本。输出严格 JSON。

字段约定（用于与 discipline_plan.json、build_html.py 对齐）：
- `discipline` 填学科 id（如 psychology、literary_studies），必须与
  `knowledge/disciplines.yaml` 的 `id` 完全一致。
- `name` 填学科显示名（如“心理学/精神分析”）。

输入：
- 文件：{{FILE_NAME}}
- 正文或全局特征：{{CONTENT_OR_FEATURES}}
- 已抽取统计：{{STATS}}
- 已抽取引用：{{QUOTES}}
- 已抽取时间线：{{TIMELINE}}

## 八要素（缺一不可，均须非空且有实质内容）

1. **core_questions**：3-5 个该学科最核心的问题。
2. **concepts**：关键概念/理论，每个解释为何适用于本文本，标注来源。
3. **methods**：说明使用方法，**≥200 字**，解释为何选这些方法、如何操作。
4. **evidence**：至少 3 条原文证据，标注文件与段落，每条附 interpretation。
5. **analysis**：解释这些证据如何回答学科问题，**≥1500 字**。必须是针对本篇的
   具体论证，禁止套话；每一条判断都要落到原文证据上。
6. **counter_evidence**：反证或替代解释，**≥300 字**。必须与 `analysis` 对话——
   指出 analysis 的哪些结论可能被推翻、存在哪些竞争解释，不能泛泛而谈。
7. **confidence**：置信度 高/中/低。
8. **references**：学科知识来源（作者、书名/论文、年份、页码/URL）。若未检索，
   标注“未检索，需核验”。

## 硬性红线

- 不得编造文献、不得临床诊断、不得道德审判。
- 心理学/医学分析只能描述，不能下诊断。
- 指出局限（`limitations`）：哪些问题文本无法回答。

输出 JSON schema：
```json
{
  "discipline": "",
  "name": "",
  "core_questions": [],
  "concepts": [{"name": "", "explanation": "", "source": ""}],
  "methods": [],
  "evidence": [{"file": "", "position": "", "quote": "", "interpretation": ""}],
  "analysis": "",
  "counter_evidence": [],
  "alternative_explanations": [],
  "confidence": "",
  "references": [{"author": "", "title": "", "year": "", "page_or_url": "", "verified": true}],
  "limitations": []
}
```

## 交稿前自检（输出 JSON 前必做，不通过就改到通过）

1. 八要素（core_questions/concepts/methods/evidence/analysis/counter_evidence/confidence/
   references）是否缺一不可、全部非空且有实质内容？
2. `analysis` 是否回应了 `core_questions` 的每个问题、每条判断落到 `evidence`，且 ≥1500 字？
3. `counter_evidence` 是否真的与 `analysis` 对话（针对具体论点给反证/竞争解释），而非泛泛，且 ≥300 字？
4. `methods` 是否 ≥200 字、说明为何选这些方法、如何操作？
5. `references` 是否真实可追溯；未检索的一律标「未检索，需核验」，不得编造页码/作者？
