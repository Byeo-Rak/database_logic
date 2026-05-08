from __future__ import annotations

from pathlib import Path

from .models import PDF_NAME_PATTERN


def parse_pdf_metadata(pdf_path: Path) -> tuple[str, str | None]:
    match = PDF_NAME_PATTERN.match(pdf_path.stem)
    if not match:
        return pdf_path.stem, None
    return match.group("exam_name"), match.group("exam_date")


def build_output_path(input_root: Path, output_root: Path, pdf_path: Path) -> Path:
    relative = pdf_path.relative_to(input_root).with_suffix(".txt")
    return output_root / relative


def build_structured_output_path(
    input_root: Path, output_root: Path, pdf_path: Path, suffix: str
) -> Path:
    relative = pdf_path.relative_to(input_root).with_suffix(suffix)
    return output_root / relative


def collect_pdfs(input_root: Path, pattern: str) -> list[Path]:
    return sorted(path for path in input_root.rglob(pattern) if path.is_file())

