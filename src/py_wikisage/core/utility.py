from pathlib import Path
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