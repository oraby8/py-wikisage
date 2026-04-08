import os
import json
import re
from pathlib import Path
from litellm import completion
from rich.console import Console
from py_wikisage.core.utility import read_document

console = Console()


def process_raw_documents(raw_dir: Path, wiki_dir: Path, config: dict):
    """Read raw documents, extract concepts using LLM, and write wiki pages."""
    if not raw_dir.exists():
        console.print(f"[red]Raw directory {raw_dir} does not exist.[/red]")
        return

    assets_content = []
    papers_content = []
    repos_content = []
    web_clips_content = []
    experiments_content = []

    for file_path in raw_dir.glob("**/*"):
        if file_path.is_file() and file_path.suffix in [".txt", ".md", ".pdf"]:
            source_type = file_path.parent.name
            print(f"Source type: {source_type}")
            
            if content:
                if source_type == "assets":
                    content = read_document(file_path)
                    assets_content.append(f"--- Document: {file_path.name} ---\n{content}\n")
                elif source_type == "papers":
                    content = read_document(file_path)
                    papers_content.append(f"--- Document: {file_path.name} ---\n{content}\n")
                elif source_type == "repos":
                    repos_content.append(f"--- Document: {file_path.name} ---\n{content}\n")
                elif source_type == "web_clips":
                    web_clips_content.append(f"--- Document: {file_path.name} ---\n{content}\n")
                elif source_type == "experiments":
                    experiments_content.append(f"--- Document: {file_path.name} ---\n{content}\n")

            else:
                console.print(f"[red]No content found in {file_path}[/red]")


    combined_text = "\n".join(documents_content)

    prompt = f"""
    You are a knowledge extraction system. Analyze the following text and extract the key concepts, entities, and topics.
    For each concept, write a short, informative wiki article about it. 
    Use `[[Concept Name]]` syntax to link to other concepts you extract.
    
    Return ONLY a JSON list of objects, where each object has a "title" (string) and "content" (string formatted as markdown).
    
    Text to analyze:
    {combined_text}
    """

    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai")
    model_name = llm_config.get("model", "gpt-4o-mini")
    model_id = f"{provider}/{model_name}" if provider != "openai" else model_name
    # Support both direct API key and env-var indirection from config.
    # - llm.api_key: literal key string
    # - llm.api_key_env: env var name that contains the key
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

        response = completion(
            **completion_kwargs,
        )

        response_content = response.choices[0].message.content

        # litellm json mode sometimes wraps in an object like {"concepts": [...]} or just returns list.
        # Let's parse it safely
        try:
            parsed_data = json.loads(response_content)
            if isinstance(parsed_data, dict):
                # Try to find the list inside
                for val in parsed_data.values():
                    if isinstance(val, list):
                        concepts = val
                        break
                else:
                    concepts = [parsed_data]
            else:
                concepts = parsed_data
        except json.JSONDecodeError:
            console.print("[red]Failed to parse JSON from LLM response[/red]")
            return

        wiki_dir.mkdir(exist_ok=True)

        for concept in concepts:
            title = concept.get("title")
            content = concept.get("content")
            if not title or not content:
                continue

            # Sanitize filename
            filename = re.sub(r"[^\w\-_\. ]", "_", title).replace(" ", "_") + ".md"
            file_path = wiki_dir / filename

            with open(file_path, "w") as f:
                f.write(f"# {title}\n\n{content}\n")

            console.print(f"Created concept page: [bold]{filename}[/bold]")

    except Exception as e:
        console.print(f"[red]Error during LLM compilation: {e}[/red]")
