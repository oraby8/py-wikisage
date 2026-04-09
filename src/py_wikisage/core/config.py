import re
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "version": 1,
    "project": "py-wikisage-project",
    "sources": {"path": "raw"},
    "output": "wiki",
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    # qmd collection name for search/query/embed (default: parent-dir + project folder).
    "qmd": {
        "collection": None,
    },
    # Optional: batched web research (research-gaps). web_provider: tavily or omit.
    "research": {
        "web_provider": None,
        "web_api_key_env": "TAVILY_API_KEY",
    },
}


def _sanitize_qmd_collection(name: str) -> str:
    """qmd collection names: lowercase letters, digits, hyphens (dots → hyphens)."""
    s = name.lower().strip()
    s = s.replace(".", "-")
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "wikisage"


def default_qmd_collection_slug(project_root: Path) -> str:
    """
    Default qmd collection name: `<parent>-<folder>` when the parent directory has a
    name, else just the folder name. Reduces collisions (many repos are named
    `research`, `notes`, `wiki`, etc. in qmd's global index).
    """
    r = project_root.resolve()
    pname = r.parent.name
    # Parent of filesystem root has no name → pname empty → use folder only.
    if pname and pname not in (".", "..") and r.name:
        return _sanitize_qmd_collection(f"{pname}-{r.name}")
    return _sanitize_qmd_collection(r.name)


def qmd_collection_name(config: dict, project_root: Path) -> str:
    """
    Stable qmd `-c` / `collection add --name` identifier for this project.
    Override with qmd.collection in config.yaml; otherwise use default_qmd_collection_slug.
    """
    q = config.get("qmd")
    if isinstance(q, dict):
        raw = q.get("collection")
        if raw is not None and str(raw).strip():
            return _sanitize_qmd_collection(str(raw).strip())
    return default_qmd_collection_slug(project_root)


def create_default_config(path: Path) -> bool:
    """
    Creates a default config.yaml at the given path.
    Returns True if created, False if it already existed.
    """
    config_file = path / "config.yaml"
    if config_file.exists():
        return False

    with open(config_file, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, sort_keys=False)

    return True


def load_config(path: Path = Path(".")) -> dict:
    config_file = path / "config.yaml"
    if not config_file.exists():
        return DEFAULT_CONFIG

    with open(config_file, "r") as f:
        return yaml.safe_load(f)
