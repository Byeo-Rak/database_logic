from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cli import parse_args
from .extractors import extract_pdf_images, extract_pdf_text
from .models import ExtractionResult
from .paths import (
    build_output_path,
    build_structured_output_path,
    collect_pdfs,
    parse_pdf_metadata,
)
from .question_parser import parse_questions_from_text
from .writers import write_manifest, write_questions_csv, write_questions_excel


def run(args: argparse.Namespace) -> int:
    input_root = Path(args.input_dir).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()
    csv_output_root = Path(args.csv_output_dir).expanduser().resolve()
    excel_output_root = Path(args.excel_output_dir).expanduser().resolve()
    image_output_root = Path(args.image_output_dir).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()

    if not input_root.exists():
        print(f"Input directory does not exist: {input_root}", file=sys.stderr)
        return 1

    pdf_files = collect_pdfs(input_root, args.glob)
    if not pdf_files:
        print(f"No PDF files found under: {input_root}", file=sys.stderr)
        return 1

    results: list[ExtractionResult] = []
    output_root.mkdir(parents=True, exist_ok=True)
    csv_output_root.mkdir(parents=True, exist_ok=True)
    excel_output_root.mkdir(parents=True, exist_ok=True)
    image_output_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdf_files:
        exam_name, exam_date = parse_pdf_metadata(pdf_path)
        exam_category = pdf_path.parent.name
        output_path = build_output_path(input_root, output_root, pdf_path)
        csv_output_path = build_structured_output_path(
            input_root, csv_output_root, pdf_path, ".csv"
        )
        excel_output_path = build_structured_output_path(
            input_root, excel_output_root, pdf_path, ".xlsx"
        )
        image_output_dir = build_structured_output_path(
            input_root, image_output_root, pdf_path, ""
        )

        if args.skip_existing and output_path.exists():
            results.append(
                ExtractionResult(
                    source_pdf=str(pdf_path),
                    output_txt=str(output_path),
                    output_csv=str(csv_output_path) if csv_output_path.exists() else None,
                    output_excel=str(excel_output_path) if excel_output_path.exists() else None,
                    output_image_dir=str(image_output_dir) if image_output_dir.exists() else None,
                    exam_category=exam_category,
                    exam_name=exam_name,
                    exam_date=exam_date,
                    pages=0,
                    text_chars=output_path.stat().st_size,
                    question_count=0,
                    image_count=0,
                    image_files=[],
                    status="skipped",
                )
            )
            print(f"[SKIP] {pdf_path}")
            continue

        try:
            text, page_count = extract_pdf_text(pdf_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")
            questions = parse_questions_from_text(text)
            image_files = extract_pdf_images(
                pdf_path=pdf_path,
                image_output_dir=image_output_dir,
                convert_to_jpg=args.convert_images_to_jpg,
            )
            write_questions_csv(csv_output_path, questions)
            write_questions_excel(excel_output_path, questions)
            result = ExtractionResult(
                source_pdf=str(pdf_path),
                output_txt=str(output_path),
                output_csv=str(csv_output_path),
                output_excel=str(excel_output_path),
                output_image_dir=str(image_output_dir),
                exam_category=exam_category,
                exam_name=exam_name,
                exam_date=exam_date,
                pages=page_count,
                text_chars=len(text),
                question_count=len(questions),
                image_count=len(image_files),
                image_files=image_files,
                status="success",
            )
            print(
                "[OK] "
                f"{pdf_path} -> {output_path}, {csv_output_path}, {excel_output_path}, "
                f"{image_output_dir} (images={len(image_files)})"
            )
        except Exception as exc:  # noqa: BLE001
            result = ExtractionResult(
                source_pdf=str(pdf_path),
                output_txt=str(output_path),
                output_csv=None,
                output_excel=None,
                output_image_dir=None,
                exam_category=exam_category,
                exam_name=exam_name,
                exam_date=exam_date,
                pages=0,
                text_chars=0,
                question_count=0,
                image_count=0,
                image_files=[],
                status="error",
                error=str(exc),
            )
            print(f"[ERROR] {pdf_path}: {exc}", file=sys.stderr)
            if args.fail_fast:
                results.append(result)
                break

        results.append(result)

    write_manifest(
        manifest_path=manifest_path,
        input_root=input_root,
        output_root=output_root,
        pdf_files=pdf_files,
        results=results,
    )

    success_count = sum(item.status == "success" for item in results)
    error_count = sum(item.status == "error" for item in results)
    skipped_count = sum(item.status == "skipped" for item in results)
    print(
        f"Completed: success={success_count}, skipped={skipped_count}, errors={error_count}"
    )
    print(f"Manifest written to: {manifest_path}")

    return 1 if error_count else 0


def main() -> int:
    return run(parse_args())

