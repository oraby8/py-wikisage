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

Configure the model in **`config.yaml`**: `llm.provider`, `llm.model`, and `llm.api_key` or `llm.api_key_env`.

## qmd (optional)

```bash
npm install -g @tobilu/qmd
# or: bun install -g @tobilu/qmd
```

## Development

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest
```
