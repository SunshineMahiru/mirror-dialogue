# 单篇分析子提示词（Map）

请只分析以下单篇随笔/日记。输出严格 JSON，不要输出多余解释。

文件：{{FILE_NAME}}
正文：
{{CONTENT}}

要求（深度优先，禁止一笔带过）：

1. 提取标题、推测日期、字数、中文字符、段落、句子、平均句长、阅读时长。

2. 摘要（`summary`）：**1200-1500 字**，必须覆盖四点：
   - 核心主题（这篇写了什么）
   - 思想主旨（作者想表达/证明/解决什么）
   - 文本在整体中的位置（它在三份文件或文集里的角色：情感层/创伤层/理性层？）
   - 与该作者其他文本的关联（哪些母题、概念、意象在此出现或由此发展）
   禁止用"以XX为核心""体现XX主旨"这类模板套话；每一句判断都必须落到本篇独有的具体内容与原文位置。

3. 分析语言风格：叙事/抒情/议论/意识流、人称、时态、句法、修辞、标点节奏，
   并给出原文例句佐证。

4. 情感基调与情绪转折：`emotion_turning_points` 字段另写 **≥300 字**，标注至少
   3 个情绪转折点，每点给出原文位置（段落号）与前后情绪对比。

5. 镜面对话分析（`mirror_dialogue`，独立小节，**≥500 字兜底 + 六要素全覆盖**，见
   `methodology/depth.md`），必须逐项回答：
   - **对话对象识别**（`addressee`）：作者在对谁说话？过去的我/未来的我/某人/上帝/
     命运/读者/物品/城市/抽象概念——给出判断依据。
   - **代词指认**（`pronoun_map`）：「你/他/她/我们」各指谁，至少 3 处原文例证，
     每条附原文与段落号。
   - **自我称谓变化**（`self_naming_change`）：我/自己/本人/俺/笔者/你自称/我们如何
     切换，至少 3 处变化实例，每条说明变化的意义。
   - **自我对话模式**（`self_talk`）：自我审判、自我安抚、自我追问、自我鼓励如何
     交替，四种各至少 1 处具体场景，每条附原文与段落号。
   - **未说出口的话**（`unsaid`）：沉默分析——从省略号、破折号、断裂句、回避话题
     中提炼作者回避表达的内容。
   - **对话对象移动轨迹**（`addressee_trajectory`）：从谁开始，到谁结束，中间经过谁。

6. 关键词：提取 5-15 个，标注频次与示例句（示例句来自原文，不是空泛释义）。

7. 引用分析（`quote_analysis` 字段，**≥300 字**）：逐条解读引用的功能
   （佐证/抒情/反讽/共鸣/逃避/权威/对话/装饰/自我安慰），**不是罗列**，每条功能
   必须结合该引用的具体上下文说明，禁止笼统说"起到抒情作用"。

8. 原文引用（`quotes`，**≥8 条**）：每条必须有 `interpretation`（解读），不得只列
   引用不解读；`position` 标注段落号；`source_guess` 不明写"不明"。

9. 所有推断标注"推断"，证据不足标注"证据不足"。

输出 JSON schema：
```json
{
  "file": "",
  "title": "",
  "date_guess": "",
  "stats": {},
  "summary": "",
  "themes": [],
  "style": {},
  "emotion": {"tone": "", "curve": [], "evidence": []},
  "emotion_turning_points": "",
  "mirror_dialogue": {
    "addressee": "",
    "addressee_trajectory": "",
    "pronoun_map": [{"pronoun": "", "referent": "", "example": "", "position": ""}],
    "self_naming_change": [{"from": "", "to": "", "meaning": "", "example": "", "position": ""}],
    "self_talk": [{"type": "", "scene": "", "example": "", "position": ""}],
    "unsaid": "",
    "conflicts": [],
    "responses": []
  },
  "keywords": [{"word": "", "count": 0, "evidence": ""}],
  "quotes": [{"text": "", "position": "", "source_guess": "", "function": "", "interpretation": ""}],
  "quote_analysis": "",
  "evidence": [],
  "uncertainty": []
}
```

## 交稿前自检（输出 JSON 前必做，不通过就改到通过）

1. `summary` 是否覆盖四点（核心主题 / 思想主旨 / 在整体中的位置 / 与他篇关联），且 ≥1200 字？
2. `mirror_dialogue` 六要素（addressee / pronoun_map / self_naming_change / self_talk /
   unsaid / addressee_trajectory）是否逐项回答，展开 ≥500 字？
3. `quotes` 是否 ≥8 条、每条有 `interpretation`、`position` 标注段落号？
4. 每条判断是否落到本篇独有的具体句子/段落，而非「以XX为核心」式模板套话？
5. 是否存在自相矛盾的判断（前后对同一现象评价相反）？
