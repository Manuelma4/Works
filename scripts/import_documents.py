import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from docx import Document


def extract_docx(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: import_documents.py <french-letter.docx> <english-letter.docx>")
    french_path = Path(sys.argv[1]).resolve()
    english_path = Path(sys.argv[2]).resolve()
    output = Path(__file__).resolve().parents[1] / "app" / "data" / "writing_examples.json"
    payload = {
        "schema_version": 1,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "note": "Tone references only. The professional profile remains the source of facts.",
        "fr": {"source": str(french_path), "text": extract_docx(french_path)},
        "en": {"source": str(english_path), "text": extract_docx(english_path)},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported writing examples to {output}")


if __name__ == "__main__":
    main()

