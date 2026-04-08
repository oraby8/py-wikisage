import os
import json
import re
from pathlib import Path
from litellm import completion
from rich.console import Console
from py_wikisage.core.utility import read_document
from py_wikisage.core.prompts import get_extraction_prompt, get_synthesis_prompt

console = Console()


def extract_concepts_from_document(
    content: str, filename: str, category: str, config: dict
) -> list[dict]:
    prompt_template = get_extraction_prompt(category)

    prompt = f"{prompt_template}\n\nDocument ({filename}):\n{content}"

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai")
    model_name = llm_config.get("model", "gpt-4o-mini")
    model_id = f"{provider}/{model_name}" if provider != "openai" else model_name

    api_key = llm_config.get("api_key")
    api_key_env = llm_config.get("api_key_env")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)

    try:
        completion_kwargs = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        elif provider == "gemini":
            console.print(
                "[yellow]No API key resolved. Set llm.api_key or export the env var named in llm.api_key_env.[/yellow]"
            )

        response = completion(**completion_kwargs)
        response_content = response.choices[0].message.content

        # litellm json mode sometimes wraps in an object like {"concepts": [...]} or just returns list.
        try:
            parsed_data = json.loads(response_content)
            if isinstance(parsed_data, dict):
                for val in parsed_data.values():
                    if isinstance(val, list):
                        concepts = val
                        break
                else:
                    concepts = [parsed_data]
            else:
                concepts = parsed_data
            return concepts
        except json.JSONDecodeError:
            console.print(
                f"[red]Failed to parse JSON from LLM response for {filename}[/red]"
            )
            return []

    except Exception as e:
        console.print(f"[red]Error during LLM extraction for {filename}: {e}[/red]")
        return []


def synthesize_wiki_articles(raw_concepts: list[dict], config: dict) -> list[dict]:
    if not raw_concepts:
        return []

    prompt_template = get_synthesis_prompt()
    concepts_json = json.dumps(raw_concepts, indent=2)
    prompt = f"{prompt_template}\n\nExtracted Concepts:\n{concepts_json}"

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai")
    model_name = llm_config.get("model", "gpt-4o-mini")
    model_id = f"{provider}/{model_name}" if provider != "openai" else model_name

    api_key = llm_config.get("api_key")
    api_key_env = llm_config.get("api_key_env")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)

    try:
        completion_kwargs = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        elif provider == "gemini":
            console.print(
                "[yellow]No API key resolved. Set llm.api_key or export the env var named in llm.api_key_env.[/yellow]"
            )

        console.print("[cyan]Synthesizing concepts into final wiki articles...[/cyan]")
        response = completion(**completion_kwargs)
        response_content = response.choices[0].message.content

        try:
            parsed_data = json.loads(response_content)
            if isinstance(parsed_data, dict):
                for val in parsed_data.values():
                    if isinstance(val, list):
                        articles = val
                        break
                else:
                    articles = [parsed_data]
            else:
                articles = parsed_data
            return articles
        except json.JSONDecodeError:
            console.print(
                "[red]Failed to parse JSON from LLM response during synthesis[/red]"
            )
            return []

    except Exception as e:
        console.print(f"[red]Error during LLM synthesis: {e}[/red]")
        return []


def process_raw_documents(raw_dir: Path, wiki_dir: Path, config: dict):
    """Read raw documents, extract concepts using LLM, and return all extracted concepts."""
    if not raw_dir.exists():
        console.print(f"[red]Raw directory {raw_dir} does not exist.[/red]")
        return []

    all_extracted_concepts: list[dict] = []

    for file_path in raw_dir.glob("**/*"):
        if file_path.is_file() and file_path.suffix in [".txt", ".md", ".pdf"]:
            category = file_path.parent.name
            console.print(
                f"Processing document: [bold]{file_path.name}[/bold] (Category: {category})"
            )

            content = read_document(file_path)
            if content:
                concepts = extract_concepts_from_document(
                    content, file_path.name, category, config
                )
                all_extracted_concepts.extend(concepts)
            else:
                console.print(f"[red]No content found in {file_path}[/red]")

    final_articles = synthesize_wiki_articles(all_extracted_concepts, config)

    if final_articles:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for article in final_articles:
            title = article.get("title", "Untitled")
            content = article.get("content", "")

            # Sanitize filename
            safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
            file_path = wiki_dir / f"{safe_title}.md"

            file_path.write_text(content)
            console.print(f"[green]Wrote synthesized article: {file_path.name}[/green]")

    return final_articles
