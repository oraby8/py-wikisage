import os
import json
import re
from pathlib import Path
from litellm import completion
from rich.console import Console

console = Console()


def read_document(file_path: Path) -> str:
    """Read content from supported document types."""
    # MVP: support txt and md
    if file_path.suffix in [".txt", ".md"]:
        return file_path.read_text()
    elif file_path.suffix == ".pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        except ImportError:
            console.print(
                "[yellow]PyMuPDF not installed, skipping PDF reading.[/yellow]"
            )
            return ""
    return ""


def process_raw_documents(raw_dir: Path, wiki_dir: Path, config: dict):
    """Read raw documents, extract concepts using LLM, and write wiki pages."""
    if not raw_dir.exists():
        console.print(f"[red]Raw directory {raw_dir} does not exist.[/red]")
        return

    documents_content = []
    for file_path in raw_dir.glob("**/*"):
        if file_path.is_file() and file_path.suffix in [".txt", ".md", ".pdf"]:
            content = read_document(file_path)
            if content:
                documents_content.append(
                    f"--- Document: {file_path.name} ---\n{content}\n"
                )

    if not documents_content:
        console.print("No readable documents found in raw/")
        return

    combined_text = "\n".join(documents_content)

    prompt = f"""
    You are a knowledge extraction system. Analyze the following text and extract the key concepts, entities, and topics.
    For each concept, write a short, informative wiki article about it. 
    Use `[[Concept Name]]` syntax to link to other concepts you extract.
    
    Return ONLY a JSON list of objects, where each object has a "title" (string) and "content" (string formatted as markdown).
    
    Text to analyze:
    {combined_text}
    """

    provider = config.get("llm", {}).get("provider", "openai")
    model_name = config.get("llm", {}).get("model", "gpt-4o-mini")
    model_id = f"{provider}/{model_name}" if provider != "openai" else model_name

    try:
        response = completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
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
