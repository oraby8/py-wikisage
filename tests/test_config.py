import copy
from pathlib import Path

from py_wikisage.core.config import (
    DEFAULT_CONFIG,
    default_qmd_collection_slug,
    qmd_collection_name,
)


def test_default_qmd_collection_slug_parent_plus_folder():
    assert default_qmd_collection_slug(Path("/Users/or/work/gec/research")) == "gec-research"


def test_default_qmd_collection_slug_fallback_when_no_parent_name():
    # POSIX root: parent "/" has empty .name → use folder only
    assert default_qmd_collection_slug(Path("/research")) == "research"


def test_qmd_collection_name_uses_default_slug():
    cfg = {"project": "ignored-title", "qmd": {"collection": None}}
    root = Path("/home/user/personal_test")
    assert qmd_collection_name(cfg, root) == "user-personal_test"


def test_qmd_collection_name_explicit_override():
    cfg = {"project": "x", "qmd": {"collection": "Custom_DB"}}
    assert qmd_collection_name(cfg, Path("/any/path")) == "custom_db"


def test_qmd_collection_name_sanitizes_composite():
    cfg = {"qmd": {"collection": None}}
    assert qmd_collection_name(cfg, Path("/a/My Vault")) == "a-my-vault"


def test_qmd_collection_name_default_config_and_folder():
    assert (
        qmd_collection_name(copy.deepcopy(DEFAULT_CONFIG), Path("/repos/py-wikisage"))
        == "repos-py-wikisage"
    )
