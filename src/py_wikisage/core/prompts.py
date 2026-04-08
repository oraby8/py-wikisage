import importlib.resources

DEFAULT_EXTRACTION_PROMPT = """
You are a knowledge extraction system. Analyze the following text and extract the key concepts, entities, and topics.
For each concept, write a short, informative summary about it. 

Return ONLY a JSON list of objects, where each object has a "title" (string) and "content" (string formatted as markdown).

Text to analyze:
{text}
"""

DEFAULT_SYNTHESIS_PROMPT = """
You are a technical writer building a knowledge base wiki.
I am providing you with a JSON list of extracted concepts from various sources.
Your job is to synthesize these concepts into cohesive, standalone wiki articles.
Merge duplicate concepts.
Use `[[Concept Name]]` syntax to link to other concepts you create.

Return ONLY a JSON list of objects, where each object has a "title" (string) and "content" (string formatted as markdown).

Raw Concepts:
{concepts}
"""


def _read_package_text(relative: str) -> str | None:
    """Load a UTF-8 text file from the installed py_wikisage package."""
    try:
        root = importlib.resources.files("py_wikisage")
    except (ModuleNotFoundError, TypeError):
        return None
    path = root / relative
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def get_extraction_prompt(category: str) -> str:
    """
    Load extraction prompt for category from package prompts/.
    Tries extract_{category}.txt, then extract_concepts.txt, then default string.
    """
    specific = _read_package_text(f"prompts/extract_{category}.txt")
    if specific is not None and specific.strip():
        return specific

    generic = _read_package_text("prompts/extract_concepts.txt")
    if generic is not None and generic.strip():
        return generic

    return DEFAULT_EXTRACTION_PROMPT


def get_synthesis_prompt() -> str:
    """Load synthesis prompt from prompts/write_article.txt or built-in default."""
    text = _read_package_text("prompts/write_article.txt")
    if text is not None and text.strip():
        return text

    return DEFAULT_SYNTHESIS_PROMPT
