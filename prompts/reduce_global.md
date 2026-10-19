# 全局综合子提示词（Reduce）

你是全局综合分析师。输入是所有单篇 analysis JSON、stats.json、keywords.json、
quotes.json、timeline.json。

请输出 global_analysis.json，包含：

1. **summary**：三份/多份文件的定位与关系（底层情感层→中层抒情→顶层理性层之类），
   一段话讲清它们如何构成一个整体。

2. **total**：文件数、总字数、中文字符、段落、句子、时间范围、写作频率。

3. **theme_clusters**：主题聚类**按语义层分组，不按文件分组**。语义层为：
   认识论（如何认识世界/自我）、价值论（什么值得追求）、伦理（如何对待他人）、
   公共（体制/社会/公考）、存在（意义/死亡/自由意志）。每群给出名称、语义层、
   涉及文件、代表引用。

4. **emotion_curve**：按时间或篇序，标出情绪高点、低点、转折点。

5. **keywords**：概括关键词结论（认知/意义/矛盾/自由意志/他者等），说明文体差异
   如何影响词频分布。

6. **quotes**：引用总数、密度、来源分布、功能分布、重复引用、互文网络。

7. **mirror_dialogue_chapter**（镜面对话专章，**≥1500 字**，本 skill 核心诉求，不可省略）：
   - `addressee_spectrum`：把所有对话对象按出现频次和情感强度排序，附证据。
   - `self_naming_timeline`：按文件顺序，展示"我→我们→他（客体化）"的自我称谓
     演化，每阶段附原文证据。
   - `self_talk_patterns`：三种自我对话模式（审判/安抚/追问）的分布与交替规律。
   - `silence_archaeology`：未说出口的话——从省略号、破折号、断裂句、回避话题中
     提炼，每条附位置。
   - `dialogue_ethics`：作者如何对待"他者"作为对话者（承认/工具化/客体化/共处）。

8. **inter_file_relations**：跨文件关联**必须给出谱系判断**（如"情感原点→创伤档案→
   理性升华"），说明哪些母题/概念/意象如何从一篇流到另一篇。

9. **orchestration_logic**：整体编排逻辑**必须给出结构判断**（如"螺旋结构：立→证→
   返→落"），说明这套文本按什么逻辑组织（时间/主题/情绪/空间/人物），不要停留在
   "可能按时间组织"这种模糊表述。

10. **key_findings**：**≥15 条**，每条必须有证据（引用文件名与片段/段落）。

11. **limitations**：局限与不确定性。

所有结论必须引用文件名与片段。不得编造。

输出 JSON schema：
```json
{
  "summary": "",
  "total": {"files": 0, "chinese_chars": 0, "paragraphs": 0, "time_range": ""},
  "theme_clusters": [{"name": "", "layer": "", "files": [], "representative_quote": ""}],
  "emotion_curve": "",
  "keywords": {"note": ""},
  "quotes": {"total": 0, "note": ""},
  "mirror_dialogue_chapter": {
    "addressee_spectrum": [{"addressee": "", "frequency": 0, "intensity": "", "evidence": ""}],
    "self_naming_timeline": [{"file": "", "stage": "", "description": "", "evidence": ""}],
    "self_talk_patterns": {"judgment": [], "comfort": [], "inquiry": [], "alternation": ""},
    "silence_archaeology": [{"cue": "", "location": "", "unsaid": ""}],
    "dialogue_ethics": ""
  },
  "inter_file_relations": "",
  "orchestration_logic": "",
  "key_findings": [],
  "limitations": []
}
```

## 交稿前自检（输出 JSON 前必做，不通过就改到通过）

1. `mirror_dialogue_chapter` 五部分（addressee_spectrum / self_naming_timeline /
   self_talk_patterns / silence_archaeology / dialogue_ethics）是否齐全、≥1500 字？
   **字段名必须是 `mirror_dialogue_chapter`，不能是 `mirror_dialogue_overview`。**
2. `key_findings` 是否 ≥15 条、每条附文件与片段证据？
3. `inter_file_relations` 是否给出明确的谱系判断（母题/概念如何从一篇流向另一篇）？
