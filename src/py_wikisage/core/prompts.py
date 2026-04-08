from pathlib import Path

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


def get_extraction_prompt(category: str) -> str:
    """
    Get the extraction prompt for a specific category.
    Looks for prompts/extract_{category}.txt, falls back to prompts/extract_concepts.txt,
    and finally falls back to a hardcoded default.
    """
    cwd = Path.cwd()
    prompts_dir = cwd / "src" / "py_wikisage" / "prompts"

    # Try specific prompt
    specific_prompt_path = prompts_dir / f"extract_{category}.txt"
    if specific_prompt_path.exists():
        return specific_prompt_path.read_text()

    # Try generic fallback
    generic_prompt_path = prompts_dir / "extract_concepts.txt"
    if generic_prompt_path.exists():
        return generic_prompt_path.read_text()

    # Hardcoded fallback
    return DEFAULT_EXTRACTION_PROMPT


def get_synthesis_prompt() -> str:
    """
    Get the synthesis prompt.
    Looks for prompts/write_article.txt, falls back to a hardcoded default.
    """
    cwd = Path.cwd()
    prompts_dir = cwd / "src" / "py_wikisage" / "prompts"

    synthesis_prompt_path = prompts_dir / "write_article.txt"
    if synthesis_prompt_path.exists():
        return synthesis_prompt_path.read_text()

    return DEFAULT_SYNTHESIS_PROMPT
