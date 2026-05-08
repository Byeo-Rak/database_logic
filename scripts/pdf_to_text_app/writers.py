from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import ExtractionResult, QUESTION_FIELDS


def write_questions_csv(csv_path: Path, questions: list[dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=QUESTION_FIELDS)
        writer.writeheader()
        writer.writerows(questions)


def write_questions_excel(excel_path: Path, questions: list[dict[str, str]]) -> None:
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "openpyxl is not installed. Run `pip install -r requirements.txt` first."
        ) from exc

    excel_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "문제목록"
    sheet.append(QUESTION_FIELDS)
    for row in questions:
        sheet.append([row[key] for key in QUESTION_FIELDS])
    workbook.save(excel_path)


def write_manifest(
    manifest_path: Path,
    input_root: Path,
    output_root: Path,
    pdf_files: list[Path],
    results: list[ExtractionResult],
) -> None:
    manifest = {
        "input_dir": str(input_root),
        "output_dir": str(output_root),
        "total_files": len(pdf_files),
        "results": [asdict(item) for item in results],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

