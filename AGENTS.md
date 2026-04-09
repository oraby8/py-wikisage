# Py-WikiSage — agent schema (LLM Wiki pattern)

This file tells humans and coding agents how this vault is structured and how to maintain it. Co-evolve it as your workflow changes.

## Layers

| Layer | Path | Rule |
|-------|------|------|
| **Raw sources** | `raw/` | Immutable inputs. The LLM reads them; do not edit sources to “fix” the wiki—fix the wiki. |
| **Wiki** | `wiki/` | Generated and maintained markdown. Interlink with `[[Page Title]]` wikilinks where helpful. |
| **Machine files** | `wiki/index.md`, `wiki/log.md` | Regenerated or appended by `py-wikisage compile`; do not hand-edit unless you know what you are doing. |

Subfolders under `raw/` (e.g. `papers/`, `articles/`, `repos/`, `experiments/`, `assets/`, `web_clips/`) categorize sources. Drop new files there, then run compile or `py-wikisage ingest <path>`. Fetched web/arXiv clips from **`research-gaps --apply`** land in `raw/web_clips/`.

## Conventions

- **Titles**: Prefer short, stable page titles; they become `Title.md` on disk.
- **Frontmatter**: Optional YAML at the top of wiki pages for tags, dates, or Dataview (if you use Obsidian).
- **Sources**: When summarizing from raw material, cite the source filename or path in the body (e.g. “Source: `raw/papers/foo.pdf`”).
- **Contradictions**: If new material conflicts with the wiki, add a short **Contradictions / updates** section rather than silently overwriting nuance.
- **Exploratory answers**: Use `py-wikisage ask` (with `--save` when useful) so good answers become wiki pages instead of dying in chat.

## CLI workflows

1. **Init** (once): `py-wikisage init`
2. **Ingest / compile**: Add sources under `raw/`, then `py-wikisage compile` (batch) or `py-wikisage ingest path/to/file` (single file).
3. **Search**: `py-wikisage search "keywords"` (requires `qmd`)
4. **Semantic query**: `py-wikisage query "natural language"` (requires `qmd`)
5. **Ask with synthesis**: `py-wikisage ask "question"` — uses retrieval context + LLM; optional `--save wiki/notes/Answer.md`
6. **Lint**: `py-wikisage lint` — broken wikilinks and orphan pages
7. **Research gaps**: `py-wikisage research-gaps` — dry-run shows planned arXiv/web queries; **`--apply`** downloads clips to `raw/web_clips/` and runs the same ingest path as `ingest`. arXiv uses **newest-first** sorting, **~3s pacing** between API calls, **retries** on rate limits, and **dedupes** identical search strings from multiple gap targets. Tavily uses a **recent (year) time filter**. Optional **`--llm-gaps`** adds LLM-suggested queries. Web search needs `research.web_provider: tavily` and a Tavily API key (env or config).

## Config

`config.yaml` in the project root: `llm.provider`, `llm.model`, `llm.api_key` or `llm.api_key_env`. Optional `research` keys for Tavily-backed `--sources web`.

## Install qmd (optional, recommended)

Hybrid search over the wiki: `npm install -g @tobilu/qmd` (or `bun install -g @tobilu/qmd`).
