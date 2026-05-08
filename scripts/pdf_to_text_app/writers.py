from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import EXCEL_IMAGE_COUNT_FIELDS, ExtractionResult, QUESTION_FIELDS


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
    headers = [*QUESTION_FIELDS, *EXCEL_IMAGE_COUNT_FIELDS]
    sheet.append(headers)
    for row in questions:
        sheet.append([row.get(key, "") for key in headers])
    workbook.save(excel_path)


def prepare_excel_rows(
    questions: list[dict[str, str]],
    expected_count: int | None,
    image_count_map: dict[int, dict[str, int]],
) -> list[dict[str, str]]:
    by_number: dict[int, dict[str, str]] = {}
    for row in questions:
        number_raw = row.get("번호", "")
        if not number_raw.isdigit():
            continue
        by_number[int(number_raw)] = dict(row)

    if expected_count is not None and expected_count > 0:
        target_max = expected_count
    else:
        target_max = max(by_number.keys(), default=0)

    rows: list[dict[str, str]] = []
    for number in range(1, target_max + 1):
        base = by_number.get(
            number,
            {
                "번호": str(number),
                "질문": "",
                "문항1": "",
                "문항2": "",
                "문항3": "",
                "문항4": "",
                "정답": "",
                "과목": "",
            },
        )
        counts = image_count_map.get(number, {})
        base["문제이미지"] = str(counts.get("question", 0))
        base["문항1이미지"] = str(counts.get("option1", 0))
        base["문항2이미지"] = str(counts.get("option2", 0))
        base["문항3이미지"] = str(counts.get("option3", 0))
        base["문항4이미지"] = str(counts.get("option4", 0))
        rows.append(base)
    return rows


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

