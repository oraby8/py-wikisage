# Py-WikiSage

A Python CLI tool that compiles raw documents into an LLM-generated Markdown wiki, maintains **`wiki/index.md`** and **`wiki/log.md`**, and optionally uses **[qmd](https://www.npmjs.com/package/@tobilu/qmd)** for hybrid search, semantic query, and **`ask`** (retrieval + LLM answers).

## LLM Wiki pattern

This tool follows the “LLM Wiki” idea: **raw sources** stay immutable under `raw/`; the **wiki** under `wiki/` is the compounding artifact the LLM updates. New projects get **`AGENTS.md`** at the repo root—a schema for you and your coding agent (workflows, conventions, CLI commands). Co-edit it as your process evolves.

## Commands

| Command | Purpose |
|---------|---------|
| `py-wikisage init` | Create `raw/`, `wiki/`, `config.yaml`, `AGENTS.md`, category folders |
| `py-wikisage compile` | Batch: extract from new raw files, synthesize with **existing wiki** context, write pages, refresh **index**, append **log**, update qmd if installed |
| `py-wikisage ingest PATH` | Same pipeline for **one file** under `raw/` (re-ingests even if seen before) |
| `py-wikisage search "…"` | qmd keyword search |
| `py-wikisage query "…"` | qmd semantic query (raw retrieval output) |
| `py-wikisage ask "…"` | qmd context + LLM answer with citations; `--save notes/answer.md` to file into wiki |
| `py-wikisage lint` | Broken `[[wikilinks]]` and orphan pages (plus index links) |
| `py-wikisage research-gaps` | **Dry-run by default:** plan arXiv (and optional Tavily web) queries from broken wikilinks; **`--apply`** fetches into `raw/web_clips/`, then ingests like `ingest`. arXiv uses **newest submissions first**, **~3s spacing** between calls, and **retries** on 429/timeouts (60s timeout); duplicate gap targets that map to the same search string only hit the API once. Tavily uses a **past-year** time filter. Use `--llm-gaps` for extra LLM-suggested queries |

## Config (`config.yaml`)

- **Where:** In the **project root** (same directory you run `py-wikisage` from). `py-wikisage init` creates **`config.yaml`** if it is missing.
- **How to edit:** Open the file in any text editor. It is **YAML**—use spaces for indentation, keep string values quoted if they contain special characters (`:`, `#`, etc.).
- **When it applies:** Each CLI command **reloads** `config.yaml` from the current working directory; save the file and run the next command—no separate restart step.

**LLM (required for `compile`, `ingest`, `ask`, and `research-gaps --llm-gaps`):** under **`llm`**, set **`provider`** and **`model`** (LiteLLM-style, e.g. `openai` + `gpt-4o-mini`, or another [supported provider](https://docs.litellm.ai/docs/providers)). Provide a key in one of two ways:

- **`api_key_env`:** name of an environment variable that holds the secret (recommended). Example: `OPENAI_API_KEY`.
- **`api_key`:** paste the key directly in the file (works, but avoid committing the file to git).

**Optional `research`** (for `research-gaps --sources web`): set **`web_provider: tavily`**, then either **`web_api_key_env`** (default env name `TAVILY_API_KEY`) or **`web_api_key`**.

**qmd** (`search`, `query`, `ask`, indexing): optional **`qmd.collection`** names the qmd index (`qmd … -c <name>`). If unset, the default is **`<parent-folder>-<project-folder>`** (e.g. `…/gec/research` → **`gec-research`**) so common names like `research` or `wiki` do not collide with other projects in qmd’s global index. If search/query stay empty after compile, run **`qmd collection list`** and ensure your wiki path matches this project; set **`qmd.collection`** explicitly if needed. Legacy single-name **`wiki`** collection: set **`qmd.collection: wiki`** in config.

Example skeleton:

```yaml
version: 1
project: my-wiki
sources:
  path: raw
output: wiki
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  # api_key: sk-...   # optional alternative to api_key_env
qmd:
  collection: null
research:
  web_provider: null
  web_api_key_env: TAVILY_API_KEY
```

## qmd (optional)

Per-project collection (see **`qmd.collection`** above); `init` / `compile` / `ingest` register `wiki/` under that name when qmd is installed.

```bash
npm install -g @tobilu/qmd
# or: bun install -g @tobilu/qmd
```

## Development

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest
```
