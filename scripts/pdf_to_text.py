#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


PDF_NAME_PATTERN = re.compile(r"^(?P<exam_name>.+?)(?P<exam_date>\d{8})")
QUESTION_FIELDS = ["번호", "질문", "문항1", "문항2", "문항3", "문항4", "정답", "과목"]


@dataclass
class ExtractionResult:
    source_pdf: str
    output_txt: str
    output_csv: str | None
    output_excel: str | None
    output_image_dir: str | None
    exam_category: str
    exam_name: str
    exam_date: str | None
    pages: int
    text_chars: int
    question_count: int
    image_count: int
    image_files: list[str]
    status: str
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert exam PDFs into text files and a JSON manifest."
    )
    parser.add_argument(
        "--input-dir",
        default="실기 시험",
        help="Root directory containing PDF files.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/text",
        help="Directory where extracted text files will be stored.",
    )
    parser.add_argument(
        "--csv-output-dir",
        default="output/csv",
        help="Directory where parsed CSV files will be stored.",
    )
    parser.add_argument(
        "--excel-output-dir",
        default="output/excel",
        help="Directory where parsed Excel files will be stored.",
    )
    parser.add_argument(
        "--image-output-dir",
        default="output/images",
        help="Directory where extracted image files will be stored.",
    )
    parser.add_argument(
        "--convert-images-to-jpg",
        action="store_true",
        help="Also save a JPG version for each extracted image.",
    )
    parser.add_argument(
        "--manifest",
        default="output/text/manifest.json",
        help="Path to the JSON manifest file.",
    )
    parser.add_argument(
        "--glob",
        default="*.pdf",
        help="File glob to match inside input directory.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip PDFs whose text output already exists.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately when a PDF fails to extract.",
    )
    return parser.parse_args()


def parse_pdf_metadata(pdf_path: Path) -> tuple[str, str | None]:
    match = PDF_NAME_PATTERN.match(pdf_path.stem)
    if not match:
        return pdf_path.stem, None
    return match.group("exam_name"), match.group("exam_date")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pypdf is not installed. Run `pip install -r requirements.txt` first."
        ) from exc

    reader = PdfReader(str(pdf_path))
    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        header = f"[PAGE {index}]"
        page_texts.append(f"{header}\n{normalize_text(extracted)}")
    full_text = "\n\n".join(page_texts).strip() + "\n"
    return full_text, len(reader.pages)


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


def detect_image_extension(image_bytes: bytes, fallback_name: str) -> str:
    fallback_suffix = Path(fallback_name).suffix.lower()
    if fallback_suffix:
        return fallback_suffix

    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return ".gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    if image_bytes.startswith(b"BM"):
        return ".bmp"
    if image_bytes.startswith((b"II*\x00", b"MM\x00*")):
        return ".tiff"
    return ".bin"


def extract_pdf_images(
    pdf_path: Path,
    image_output_dir: Path,
    convert_to_jpg: bool = False,
) -> list[str]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "pypdf is not installed. Run `pip install -r requirements.txt` first."
        ) from exc

    image_converter = None
    if convert_to_jpg:
        try:
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Pillow is not installed. Run `pip install -r requirements.txt` first."
            ) from exc
        image_converter = Image

    reader = PdfReader(str(pdf_path))
    image_output_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[str] = []

    for page_index, page in enumerate(reader.pages, start=1):
        page_images = list(page.images)
        for image_index, image_item in enumerate(page_images, start=1):
            image_name = getattr(image_item, "name", f"image_{image_index}")
            image_data = getattr(image_item, "data", b"")
            if not image_data:
                continue

            image_suffix = detect_image_extension(image_data, image_name)
            image_filename = f"page_{page_index:03d}_img_{image_index:02d}{image_suffix}"
            image_path = image_output_dir / image_filename
            image_path.write_bytes(image_data)
            saved_files.append(str(image_path))

            if image_converter is None:
                continue
            if image_suffix in {".jpg", ".jpeg"}:
                continue

            try:
                with image_converter.open(io.BytesIO(image_data)) as img:
                    rgb_image = img.convert("RGB")
                    jpg_path = image_path.with_suffix(".jpg")
                    rgb_image.save(jpg_path, format="JPEG", quality=92)
                    saved_files.append(str(jpg_path))
            except Exception:
                # 손상 이미지 또는 변환 불가 포맷은 원본 저장만 유지
                pass

    return saved_files


def clean_question_text(raw_text: str) -> str:
    lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[PAGE "):
            continue
        if "전자문제집 CBT : www.comcbt.com" in stripped:
            continue
        if stripped.startswith("최강 자격증 기출문제"):
            continue
        lines.append(stripped)
    text = " ".join(lines)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # PDF 추출 과정에서 숫자가 붙는 경우(예: 10129., 379.)를 분리해 문제 번호 인식을 돕는다.
    text = re.sub(r"(?<=\d{2})(?=(\d{2}\.\s))", " ", text)
    text = re.sub(r"([④❹]\s*\d)(\d{2}\.\s)", r"\1 \2", text)
    return text


def extract_subject_map(raw_text: str) -> dict[int, str]:
    subject_map: dict[int, str] = {}
    for match in re.finditer(r"(\d+)\s*과목\s*:\s*([^\n\r]+)", raw_text):
        index = int(match.group(1))
        name = match.group(2).strip()
        if index not in subject_map:
            subject_map[index] = name
    return subject_map


def normalize_compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_questions_from_text(raw_text: str) -> list[dict[str, str]]:
    cleaned = clean_question_text(raw_text)
    subject_map = extract_subject_map(raw_text)
    question_pattern = re.compile(r"(?<!\d)(\d{1,3})\.\s*(.*?)(?=(?<!\d)(\d{1,3})\.\s|$)")
    option_pattern = re.compile(
        r"[①❶]\s*(.*?)\s*[②❷]\s*(.*?)\s*[③❸]\s*(.*?)\s*[④❹]\s*(.*)",
        re.DOTALL,
    )

    questions: list[dict[str, str]] = []
    for question_match in question_pattern.finditer(cleaned):
        number = int(question_match.group(1))
        body = normalize_compact(question_match.group(2))

        if number < 1 or number > 150:
            continue

        option_match = option_pattern.search(body)
        if option_match:
            stem = normalize_compact(body[: option_match.start()])
            options = [normalize_compact(option_match.group(i)) for i in range(1, 5)]
        else:
            stem = body
            options = ["", "", "", ""]

        answer = ""
        for idx, marker in enumerate(("❶", "❷", "❸", "❹"), start=1):
            if marker in body:
                answer = str(idx)
                break

        subject_idx = ((number - 1) // 20) + 1
        subject_name = subject_map.get(subject_idx, f"{subject_idx}과목")
        questions.append(
            {
                "번호": str(number),
                "질문": stem,
                "문항1": options[0],
                "문항2": options[1],
                "문항3": options[2],
                "문항4": options[3],
                "정답": answer,
                "과목": subject_name,
            }
        )

    deduped_by_number: dict[int, dict[str, str]] = {}
    for row in questions:
        q_number = int(row["번호"])
        if q_number not in deduped_by_number:
            deduped_by_number[q_number] = row

    sorted_numbers = sorted(deduped_by_number)
    if not sorted_numbers:
        return []

    under_100 = [number for number in sorted_numbers if number <= 100]
    if under_100:
        max_reasonable = max(under_100)
    else:
        max_reasonable = max(sorted_numbers)
    filtered = [
        deduped_by_number[number] for number in sorted_numbers if number <= max_reasonable
    ]
    return filtered


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


def main() -> int:
    args = parse_args()
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
                    output_excel=str(excel_output_path)
                    if excel_output_path.exists()
                    else None,
                    output_image_dir=str(image_output_dir)
                    if image_output_dir.exists()
                    else None,
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

    success_count = sum(item.status == "success" for item in results)
    error_count = sum(item.status == "error" for item in results)
    skipped_count = sum(item.status == "skipped" for item in results)
    print(
        f"Completed: success={success_count}, skipped={skipped_count}, errors={error_count}"
    )
    print(f"Manifest written to: {manifest_path}")

    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
