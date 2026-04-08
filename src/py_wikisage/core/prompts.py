from pathlib import Path


def get_prompt(filename_or_category: str, default_text: str) -> str:
    prompt_path = Path("prompts") / filename_or_category
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return default_text


def get_extraction_prompt(category: str) -> str:
    prompt_path = Path("prompts") / f"extract_{category}.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    fallback_path = Path("prompts") / "extract_concepts.txt"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")

    return "Extract concepts from the following text."


def get_synthesis_prompt() -> str:
    prompt_path = Path("prompts") / "write_article.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    return "Write an article based on the provided information."
