from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
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
from .question_parser import get_missing_question_numbers, parse_questions_from_text
from .writers import (
    prepare_excel_rows,
    write_manifest,
    write_questions_excel,
)

try:
    import sys
    parent_path = Path(__file__).resolve().parent.parent
    if str(parent_path) not in sys.path:
        sys.path.insert(0, str(parent_path))
    from firebase_sync.id_mapper import resolve_certification_meta, resolve_course_id
except ImportError:
    # id_mapper를 찾을 수 없으면 기본값 사용
    def resolve_certification_meta(subject_key):
        class Meta:
            certification_id = "InfoProcessEngineer"
            certification_name = "정보처리기사"
        return Meta()
    def resolve_course_id(cert_id, course_name):
        return "Unknown"


EXPECTED_QUESTION_COUNTS = {
    "정처기": 100,
    "산업안전": 120,
    "컴활1급": 60,
    "컴활2급": 40,
}
PAGE_MARKER_PATTERN = re.compile(r"\[PAGE\s+(?P<page>\d+)\]")
QUESTION_NUMBER_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\.\s")
IMAGE_NAME_PATTERN = re.compile(r"^page_(?P<page>\d{3})_img_(?P<idx>\d{2})")
# 새로운 Firebase Storage 스타일 이미지 파일명 패턴 (예: question-1.jpg)
# 경로: images/{cert}/{company}/{round-subject}/{qno}/question-1.jpg
FIREBASE_IMAGE_PATH_PATTERN = re.compile(
    r"[/\\](?P<qno>\d{3})[/\\](?P<slot>question|option[1-4])-(?P<idx>\d+)"
)


def normalize_nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def get_expected_question_count(exam_category: str) -> int | None:
    return EXPECTED_QUESTION_COUNTS.get(normalize_nfc(exam_category))


def build_page_questions_map(raw_text: str) -> dict[int, list[int]]:
    pieces = PAGE_MARKER_PATTERN.split(raw_text)
    page_map: dict[int, list[int]] = {}
    for idx in range(1, len(pieces), 2):
        page_no = int(pieces[idx])
        page_body = pieces[idx + 1] if idx + 1 < len(pieces) else ""
        seen: set[int] = set()
        ordered_numbers: list[int] = []
        for match in QUESTION_NUMBER_PATTERN.finditer(page_body):
            number = int(match.group(1))
            if number < 1 or number > 150:
                continue
            if number in seen:
                continue
            seen.add(number)
            ordered_numbers.append(number)
        page_map[page_no] = ordered_numbers
    return page_map


def map_question_image_counts(
    raw_text: str,
    image_paths: list[str],
) -> dict[int, dict[str, int]]:
    """이미지 파일 경로를 분석하여 각 문제의 이미지 개수를 계산합니다.
    
    구버전 형식(page_001_img_01.jpg)과 신규 형식(images/.../001/question-1.jpg) 모두 지원합니다.
    """
    page_map = build_page_questions_map(raw_text)
    
    # 신규 형식 (images/.../001/question-1.jpg) 먼저 확인
    counts_from_new_format: dict[int, dict[str, int]] = defaultdict(
        lambda: {"question": 0, "option1": 0, "option2": 0, "option3": 0, "option4": 0}
    )
    has_new_format = False
    
    for raw_path in image_paths:
        path_str = str(raw_path).replace("\\", "/")
        match = FIREBASE_IMAGE_PATH_PATTERN.search(path_str)
        if match:
            has_new_format = True
            question_no = int(match.group("qno"))
            slot = match.group("slot")
            
            if question_no not in counts_from_new_format:
                counts_from_new_format[question_no] = {
                    "question": 0, "option1": 0, "option2": 0, "option3": 0, "option4": 0
                }
            counts_from_new_format[question_no][slot] += 1
    
    # 신규 형식이 있으면 그것을 사용
    if has_new_format:
        return dict(counts_from_new_format)
    
    # 신규 형식이 없으면 구버전 방식 사용
    grouped_by_page: dict[int, list[tuple[int, Path]]] = defaultdict(list)
    for raw_path in image_paths:
        path = Path(raw_path)
        match = IMAGE_NAME_PATTERN.match(path.name)
        if not match:
            continue
        page = int(match.group("page"))
        idx = int(match.group("idx"))
        grouped_by_page[page].append((idx, path))

    per_question_total: dict[int, int] = defaultdict(int)
    for page, items in grouped_by_page.items():
        items.sort(key=lambda item: item[0])
        question_numbers = page_map.get(page, [])
        if not question_numbers:
            continue
        for zero_based, _ in enumerate(items):
            question_idx = min(zero_based, len(question_numbers) - 1)
            question_no = question_numbers[question_idx]
            per_question_total[question_no] += 1

    counts: dict[int, dict[str, int]] = {}
    for question_no, total in per_question_total.items():
        question_count = 0
        option_counts = [0, 0, 0, 0]
        if total == 1:
            question_count = 1
        elif total > 1:
            question_count = 1
            option_take = min(4, total - 1)
            for idx in range(option_take):
                option_counts[idx] = 1
            if total - 1 > 4:
                question_count += (total - 1 - 4)

        counts[question_no] = {
            "question": question_count,
            "option1": option_counts[0],
            "option2": option_counts[1],
            "option3": option_counts[2],
            "option4": option_counts[3],
        }
    return counts


def run(args: argparse.Namespace) -> int:
    input_root = Path(args.input_dir).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()
    excel_output_root = Path(args.excel_output_dir).expanduser().resolve()
    image_output_root = Path(args.image_output_dir).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    validation_log_path = output_root / "question_validation.log"

    if not input_root.exists():
        print(f"Input directory does not exist: {input_root}", file=sys.stderr)
        return 1

    pdf_files = collect_pdfs(input_root, args.glob)
    if not pdf_files:
        print(f"No PDF files found under: {input_root}", file=sys.stderr)
        return 1

    results: list[ExtractionResult] = []
    validation_issues: list[dict[str, object]] = []
    output_root.mkdir(parents=True, exist_ok=True)
    excel_output_root.mkdir(parents=True, exist_ok=True)
    image_output_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdf_files:
        exam_name, exam_date = parse_pdf_metadata(pdf_path)
        exam_category = pdf_path.parent.name
        expected_count = get_expected_question_count(exam_category)
        
        # 인증 정보 추출
        cert_meta = resolve_certification_meta(exam_category)
        certification_id = cert_meta.certification_id
        
        # 회차 정보 추출 (날짜에서 연도와 월로 판단)
        round_id = ""
        if exam_date and len(exam_date) >= 6:
            year = exam_date[:4]
            month = exam_date[4:6]
            # 3월: 1회차, 5월: 2회차, 8월: 3회차 (대략적 기준)
            if month in ["02", "03", "04"]:
                round_no = 1
            elif month in ["05", "06", "07"]:
                round_no = 2
            else:
                round_no = 3
            round_id = f"{year}-{round_no}"
        
        output_path = build_output_path(input_root, output_root, pdf_path)
        excel_output_path = build_structured_output_path(
            input_root, excel_output_root, pdf_path, ".xlsx"
        )
        # 이미지 출력 디렉토리는 images 루트만 사용
        image_output_dir = image_output_root

        if args.skip_existing and output_path.exists():
            results.append(
                ExtractionResult(
                    source_pdf=str(pdf_path),
                    output_txt=str(output_path),
                    output_csv=None,
                    output_excel=str(excel_output_path) if excel_output_path.exists() else None,
                    output_image_dir=str(image_output_dir) if image_output_dir.exists() else None,
                    exam_category=exam_category,
                    exam_name=exam_name,
                    exam_date=exam_date,
                    pages=0,
                    text_chars=output_path.stat().st_size,
                    question_count=0,
                    question_expected_count=expected_count,
                    missing_question_numbers=[],
                    reparsed_with_retry=False,
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

            reparsed_with_retry = False
            questions = parse_questions_from_text(text, expected_count=expected_count)
            missing_numbers = (
                get_missing_question_numbers(questions, expected_count)
                if expected_count is not None
                else []
            )

            if expected_count is not None and missing_numbers:
                retry_questions = parse_questions_from_text(
                    text,
                    expected_count=expected_count,
                    aggressive_split=True,
                )
                retry_missing = get_missing_question_numbers(
                    retry_questions, expected_count
                )
                if len(retry_missing) < len(missing_numbers):
                    questions = retry_questions
                    missing_numbers = retry_missing
                    reparsed_with_retry = True
            
            # 문제별 과목 정보 매핑 생성
            question_subject_map = {}
            last_valid_subject_id = None
            
            for q in questions:
                q_no_raw = q.get("번호", "")
                if q_no_raw.isdigit():
                    q_no = int(q_no_raw)
                    subject = q.get("과목", "").strip()
                    if subject:
                        course_id = resolve_course_id(certification_id, subject)
                        round_subject_id = f"{round_id}-{course_id}" if round_id else course_id
                        question_subject_map[q_no] = round_subject_id
                        last_valid_subject_id = round_subject_id
                    elif last_valid_subject_id:
                        # 과목 정보가 없으면 이전 문제의 과목 사용
                        question_subject_map[q_no] = last_valid_subject_id
            
            # 파싱되지 않은 문제들도 이전 과목으로 채우기
            # expected_count를 초과하는 문제도 처리 (예: 101-110번)
            max_question_no = max(
                (int(q.get("번호", 0)) for q in questions if q.get("번호", "").isdigit()),
                default=expected_count if expected_count else 0
            )
            fill_up_to = max(expected_count if expected_count else 0, max_question_no)
            
            if last_valid_subject_id and fill_up_to > 0:
                for i in range(1, fill_up_to + 1):
                    if i not in question_subject_map:
                        # 이전에 설정된 과목이 있으면 사용
                        for j in range(i - 1, 0, -1):
                            if j in question_subject_map:
                                question_subject_map[i] = question_subject_map[j]
                                break
            
            # 이미지 추출 시 메타데이터 전달
            image_files = extract_pdf_images(
                pdf_path=pdf_path,
                image_output_dir=image_output_dir,
                convert_to_jpg=args.convert_images_to_jpg,
                raw_text=text,
                certification_id=certification_id,
                company_id="CBT",
                question_subject_map=question_subject_map,
                pdf_filename=pdf_path.name,
            )
            image_count_map = map_question_image_counts(text, image_files)
            excel_rows = prepare_excel_rows(
                questions=questions,
                expected_count=expected_count,
                image_count_map=image_count_map,
            )
            write_questions_excel(excel_output_path, excel_rows)

            if expected_count is not None and missing_numbers:
                issue = {
                    "source_pdf": str(pdf_path),
                    "exam_category": normalize_nfc(exam_category),
                    "expected_count": expected_count,
                    "actual_count": len(questions),
                    "missing_numbers": missing_numbers,
                    "reparsed_with_retry": reparsed_with_retry,
                }
                validation_issues.append(issue)
                print(
                    "[WARN] "
                    f"{pdf_path} -> expected={expected_count}, actual={len(questions)}, "
                    f"missing={missing_numbers}"
                )

            result = ExtractionResult(
                source_pdf=str(pdf_path),
                output_txt=str(output_path),
                output_csv=None,
                output_excel=str(excel_output_path),
                output_image_dir=str(image_output_dir),
                exam_category=exam_category,
                exam_name=exam_name,
                exam_date=exam_date,
                pages=page_count,
                text_chars=len(text),
                question_count=len(questions),
                question_expected_count=expected_count,
                missing_question_numbers=missing_numbers,
                reparsed_with_retry=reparsed_with_retry,
                image_count=len(image_files),
                image_files=image_files,
                status="success",
            )
            print(
                "[OK] "
                f"{pdf_path} -> {output_path}, {excel_output_path}, "
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
                question_expected_count=expected_count,
                missing_question_numbers=[],
                reparsed_with_retry=False,
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

    if validation_issues:
        validation_log_path.parent.mkdir(parents=True, exist_ok=True)
        validation_log_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in validation_issues)
            + "\n",
            encoding="utf-8",
        )
        print(f"[WARN] Question validation log written: {validation_log_path}")

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

