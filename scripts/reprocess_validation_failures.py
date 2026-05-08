#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from firebase_sync.selector import detect_input_root  # pyright: ignore[reportMissingImports]
from pdf_to_text_app.pipeline import (  # pyright: ignore[reportMissingImports]
    EXPECTED_QUESTION_COUNTS,
    normalize_nfc,
    run as run_pdf_pipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reprocess PDFs listed in question_validation.log and revalidate."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root path (defaults to current directory).",
    )
    parser.add_argument(
        "--log-path",
        default="output/text/question_validation.log",
        help="Path to validation log file (JSON Lines).",
    )
    parser.add_argument(
        "--convert-images-to-jpg",
        action="store_true",
        default=True,
        help="Also generate JPG copies during reprocessing. (default: on)",
    )
    parser.add_argument(
        "--no-convert-images-to-jpg",
        dest="convert_images_to_jpg",
        action="store_false",
        help="Disable JPG conversion during reprocessing.",
    )
    return parser.parse_args()


def load_validation_entries(log_path: Path) -> list[dict[str, object]]:
    if not log_path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        entries.append(json.loads(stripped))
    return entries


def get_missing_numbers(csv_path: Path, expected_count: int) -> tuple[int, list[int]]:
    if not csv_path.exists():
        return 0, list(range(1, expected_count + 1))
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    numbers = {
        int(row["번호"]) for row in rows if row.get("번호", "").isdigit()
    }
    missing = [num for num in range(1, expected_count + 1) if num not in numbers]
    return len(numbers), missing


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    input_root = detect_input_root(project_root)
    log_path = Path(args.log_path).expanduser()
    if not log_path.is_absolute():
        log_path = (project_root / log_path).resolve()

    entries = load_validation_entries(log_path)
    if not entries:
        print(f"No validation entries found: {log_path}")
        return 0

    unique_sources: list[Path] = []
    seen: set[str] = set()
    for entry in entries:
        source_pdf = str(entry.get("source_pdf", "")).strip()
        if not source_pdf or source_pdf in seen:
            continue
        seen.add(source_pdf)
        unique_sources.append(Path(source_pdf))

    remaining_issues: list[dict[str, object]] = []
    for source_pdf in unique_sources:
        if not source_pdf.exists():
            remaining_issues.append(
                {
                    "source_pdf": str(source_pdf),
                    "error": "source_pdf_not_found",
                }
            )
            print(f"[ERROR] Source PDF not found: {source_pdf}")
            continue

        try:
            relative_pdf = source_pdf.relative_to(input_root)
            glob_pattern = relative_pdf.as_posix()
        except ValueError:
            glob_pattern = source_pdf.name

        run_args = argparse.Namespace(
            input_dir=str(input_root),
            output_dir=str(project_root / "output" / "text"),
            csv_output_dir=str(project_root / "output" / "csv"),
            excel_output_dir=str(project_root / "output" / "excel"),
            image_output_dir=str(project_root / "output" / "images"),
            manifest=str(project_root / "output" / "text" / "manifest.json"),
            glob=glob_pattern,
            skip_existing=False,
            fail_fast=True,
            convert_images_to_jpg=args.convert_images_to_jpg,
        )
        exit_code = run_pdf_pipeline(run_args)
        if exit_code != 0:
            remaining_issues.append(
                {
                    "source_pdf": str(source_pdf),
                    "error": "reprocess_failed",
                }
            )
            print(f"[ERROR] Reprocess failed: {source_pdf}")
            continue

        exam_category = normalize_nfc(source_pdf.parent.name)
        expected_count = EXPECTED_QUESTION_COUNTS.get(exam_category)
        if expected_count is None:
            continue

        csv_path = (project_root / "output" / "csv" / source_pdf.parent.name / source_pdf.with_suffix(".csv").name)
        actual_count, missing_numbers = get_missing_numbers(csv_path, expected_count)
        if missing_numbers:
            issue = {
                "source_pdf": str(source_pdf),
                "exam_category": exam_category,
                "expected_count": expected_count,
                "actual_count": actual_count,
                "missing_numbers": missing_numbers,
            }
            remaining_issues.append(issue)
            print(
                f"[WARN] still missing: {source_pdf} "
                f"expected={expected_count}, actual={actual_count}, missing={missing_numbers}"
            )
        else:
            print(f"[OK] revalidated: {source_pdf}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if remaining_issues:
        log_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in remaining_issues) + "\n",
            encoding="utf-8",
        )
    else:
        log_path.write_text("", encoding="utf-8")

    print(
        f"Reprocess completed: total={len(unique_sources)}, "
        f"remaining_issues={len(remaining_issues)}"
    )
    print(f"Validation log updated: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

