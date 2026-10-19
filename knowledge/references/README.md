# 本地学科知识库（可选）

此目录用于存放本地文献、教材、论文摘要、笔记等，供 `scripts/knowledge_lookup.py`
在 `knowledge_source: local` 模式下检索。

## 使用方式

1. 将学科资料以 `.md` / `.txt` / `.json` / `.yaml` 格式放入本目录（可建子目录分类）。
2. 在 `config.yaml` 中设置：
   ```yaml
   knowledge_source: "local"
   local_knowledge_dir: "./knowledge/references"
   ```
3. 运行 `knowledge_lookup.py --source local` 时，脚本会按概念关键词检索本目录
   文件名与内容，并记录命中文件与片段作为可追溯来源。

## 命名建议

- 按学科建子目录，例如 `psychology/`、`sociology/`、`literary_studies/`。
- 文件名建议包含概念或作者，便于检索，例如 `attachment-theory-bowlby.md`。

## 注意事项

- 若某概念在本地库未命中，来源将标记为“未检索，需核验”，不得编造文献。
- 本地资料本身也应在报告参考文献中注明作者、标题、年份、页码。
