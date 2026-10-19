# mirror-dialogue

Treat personal essays, diaries, journals, and collections as **"mirror dialogues" between the author and their self, others, time, and environment** — analyze them through multidisciplinary lenses and produce a structured, traceable HTML report.

> 中文文档见 [README.zh-CN.md](README.zh-CN.md)

## About

`mirror-dialogue` is not a generic text-analysis tool. It is a **Skill** built around a distinctive analytical lens: every text is treated as a mirror that systematically reveals *who the author is speaking to, how they name themselves, how they talk to themselves, and what they leave unsaid*. On top of that, 15 disciplinary lenses (literary studies, linguistics, psychology, sociology, history, philosophy, religious/myth studies, gender studies, ecology/space, medical humanities, media studies, education, economics/politics/law, arts, and digital humanities) are routed and cross-examined, culminating in a "depth-first" HTML report.

Core design principle: **methodology sets the skeleton, the LLM fills the flesh.** Scripts only do precise computation (character counts, word frequency, quote localization, timelines, evidence counts); content judgment (what counts as a quote, what counts as a core discipline, how to interpret mirror dialogue) is delegated to an LLM "annotation layer"; the report structure is rendered uniformly by a template.

> Design rationale, architecture layers, and market positioning: see [ARCHITECTURE.md](ARCHITECTURE.md).

## Features

- **Mirror-dialogue analysis** (core): six single-text elements (addressee / pronoun mapping / self-naming shifts / self-talk patterns / the unsaid / trajectory) plus a global chapter of five parts (addressee spectrum / self-naming timeline / self-talk patterns / archaeology of silence / dialogue ethics).
- **Multidisciplinary lenses**: 15 disciplines routed into core / secondary / excluded via `when/questions/concepts`; core disciplines get depth, secondary get brevity, excluded are explained in the appendix.
- **Cross-disciplinary synthesis**: consensus, disagreement (with "why"), complementarity, blind spots, multi-explanations (≥8 groups) for the same phenomenon, and a synthesis model.
- **Emotion dynamics** (simplified UED): per-segment VAD annotation (valence / arousal / dominance) and dynamic metrics — Home Base, Variability, Instability, Rise/Recovery Rate.
- **Quote analysis**: judging what counts as a quote, source guessing, and function analysis (must be specific to context).
- **Pre-flight gate**: `validate.py --gate-only` blocks "structurally complete but shallow" reports before HTML generation; insufficient depth is rejected by default.
- **Privacy redaction**: regex for phone / ID / email / landline plus explicit name / address lists.
- **Reference verification switch**: verify real references when online; otherwise honestly mark "not retrieved, needs verification" — never fabricate.

## Installation & Usage

### Requirements

- Python 3.12+
- Dependencies: `jieba`, `pyyaml`, `jinja2`

### Install

```bash
git clone https://github.com/SunshineMahiru/mirror-dialogue.git
cd mirror-dialogue
pip install -r requirements.txt
```

### Usage (five-stage pipeline)

`run.py` orchestrates the pipeline across five stages (script computation and LLM analysis alternate):

```bash
# Stage 1: run pure-computation scripts (ingest/stats/timeline); exits with a TODO if annotation.json is missing
python run.py --target-dir "/path/to/your/texts" --out ./output \
  --config ./config.yaml --knowledge-source builtin

# Stage 2: the LLM reads the raw texts and produces the annotation layer (annotation.json)
#          — quote candidates + discipline routing + emotion VAD annotation (see prompts/annotate.md)

# Stage 3: re-run (skip stage 1); scripts read annotation.json for precise localization & evidence counting
python run.py --target-dir "/path/to/your/texts" --skip-stage1

# Stage 4: the LLM produces the 4 analysis JSONs in batches
#          (single / global / discipline / cross; depth thresholds in methodology/depth.md)

# Stage 5: re-run once the analysis JSONs are complete; the pre-flight gate runs before build
python run.py --target-dir "/path/to/your/texts" --run-llm-check --skip-scripts
```

`run.py` arguments:

| Argument | Purpose |
|----------|---------|
| `--target-dir` | Directory of texts to analyze (required) |
| `--out` | Output directory, default `./output` |
| `--config` | Config file, default `./config.yaml` |
| `--skip-stage1` | Skip stage 1 (reuse ingest/stats/timeline artifacts) |
| `--skip-scripts` | Skip all scripts (pure build mode) |
| `--run-llm-check` | Continue to build_html when analysis JSONs are complete |
| `--force` | Force rendering even if the gate reports failures (marks the page as "substandard draft") |
| `--knowledge-source` | `network` / `local` / `builtin` |

### Run tests

```bash
python -m unittest discover tests
```

## Project Structure

```
mirror-dialogue/
├── SKILL.md              # Main spec (full workflow & hard rules)
├── run.py                # Orchestrator (five stages)
├── validate.py           # Self-check + pre-flight gate (--gate-only)
├── schema.json           # Machine-readable validation schema (depth thresholds + checklists)
├── config.yaml           # Stopwords / privacy rules / network switch / output paths
├── requirements.txt      # Dependencies
├── methodology/          # Methodology layer (9 docs: mirror-dialogue / text-analysis /
│                         #   quote-analysis / discipline-routing / report-structure /
│                         #   depth / emotion-dynamics / knowledge-rules)
├── prompts/              # Sub-prompts (7: annotate / map_single / reduce_global /
│                         #   discipline_analysis / cross_discipline / quote_analysis / verify)
├── scripts/              # Computation scripts (8: ingest / stats / quotes / timeline /
│                         #   discipline_router / emotion_dynamics / knowledge_lookup /
│                         #   build_html)
├── templates/            # HTML report template
├── knowledge/            # Discipline definitions + local reference template
├── tests/                # Unit tests (unittest)
└── .github/workflows/    # CI
```

> `output/` (analysis artifacts) and `reference-projects/` (third-party reference source) are excluded by `.gitignore`.

## Configuration

Key options in `config.yaml`:

| Option | Description |
|--------|-------------|
| `supported_extensions` | Supported text extensions (`.txt/.md/.doc/.docx`) |
| `privacy_mode` / `privacy_patterns` | Privacy redaction switch & regex (phone/ID/email/landline) |
| `privacy_names` / `privacy_addresses` | Explicit name / address redaction lists |
| `allow_network` | Whether to allow online retrieval of domain knowledge |
| `verify_references` | Reference verification switch (tied to `allow_network`; auto-off when offline, only marks "needs verification") |
| `chunk_batch` | Number of texts per Map batch |
| `min_evidence_per_core` | Minimum evidence items per core discipline |

Depth thresholds live in `schema.json` (machine-readable) and `methodology/depth.md` (human-readable), kept in sync: **depth ≠ word count — checklist coverage comes first, word count is only a floor.**

## Contributing

Issues and pull requests are welcome. Before contributing:

1. **Four-layer boundary rule**: methodology layer defines rules → annotation layer (LLM) judges → computation layer (scripts) calculates → analysis layer (LLM) interprets. **Scripts retreat to computation; judgment belongs to the LLM** — never use heuristics in scripts to decide "what counts as a quote" or "what is a core discipline".
2. **Gate consistency**: when adding a quality check, update `schema.json` (machine-readable) and `methodology/` (human-readable) together, and add matching tests.
3. **Tests**: run `python -m unittest discover tests` after changes and keep it green.
4. **Depth methodology**: any change to depth thresholds must be described centrally in `methodology/depth.md` to avoid scattered conflicting numbers.
5. **Privacy & ethics**: this project analyzes real diaries — adhere to the "describe, never diagnose" bottom line, and retain crisis-intervention notes for strongly negative emotions.

## License

This project is licensed under the [MIT License](LICENSE).
