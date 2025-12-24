from __future__ import annotations

from typing import Callable, Iterable, Tuple, List
from pypdf import PdfReader


def extract_text_from_uploads(
    uploads: Iterable,
    on_file: Callable[[str], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> Tuple[str, List[str]]:
    """Extract text from uploaded PDF files (Streamlit UploadedFile objects).

    Returns:
        combined_text: concatenated text with file headers
        names: list of filenames in the order processed
    """
    uploads = list(uploads or [])
    names: List[str] = []
    parts: List[str] = []

    total = max(1, len(uploads))
    for i, up in enumerate(uploads, start=1):
        name = getattr(up, "name", f"file_{i}.pdf")
        names.append(name)
        if on_file:
            on_file(name)

        reader = PdfReader(up)
        txt_parts = []
        for page in reader.pages:
            txt_parts.append(page.extract_text() or "")
        text = "\n".join(txt_parts).strip()

        parts.append(f"\n\n### FILE: {name}\n{text}")

        if on_progress:
            on_progress(int(i / total * 100))

    return "".join(parts).strip(), names
