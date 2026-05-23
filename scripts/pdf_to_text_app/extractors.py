from __future__ import annotations

import io
import re
from pathlib import Path


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
    raw_text: str = "",
    certification_id: str = "",
    company_id: str = "CBT",
    question_subject_map: dict[int, str] | None = None,
    pdf_filename: str = "",
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

    # 페이지별 문제 번호 매핑 생성
    page_questions_map = _build_page_questions_map(raw_text) if raw_text else {}

    reader = PdfReader(str(pdf_path))
    saved_files: list[str] = []

    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_images = list(page.images)
        except Exception:
            # 일부 PDF는 이미지 객체 파싱 도중 pypdf 내부 assertion이 발생할 수 있다.
            # 이 경우 해당 페이지 이미지는 건너뛰고 나머지 처리를 계속 진행한다.
            continue

        # 현재 페이지의 문제 번호 목록
        question_numbers = page_questions_map.get(page_index, [])
        
        for image_index, image_item in enumerate(page_images, start=1):
            image_name = getattr(image_item, "name", f"image_{image_index}")
            image_data = getattr(image_item, "data", b"")
            if not image_data:
                continue

            image_suffix = detect_image_extension(image_data, image_name)
            
            # Firebase Storage 형식으로 디렉토리 및 파일명 생성
            if question_numbers and certification_id and question_subject_map:
                # 이미지가 속한 문제 번호 결정
                question_idx = min(image_index - 1, len(question_numbers) - 1)
                question_no = question_numbers[question_idx]
                
                # 해당 문제의 과목 정보 가져오기
                round_subject_id = question_subject_map.get(question_no, "")
                
                if round_subject_id:
                    # 첫 번째 이미지는 문제 이미지, 나머지는 보기 이미지
                    if image_index == 1:
                        slot_name = "question"
                        slot_idx = 1
                    else:
                        option_no = min(image_index - 1, 4)  # 최대 4개 보기
                        slot_name = f"option{option_no}"
                        slot_idx = 1
                    
                    # Firebase Storage 구조: images/{certificationId}/{companyId}/{roundId-subjectId}/{questionNo3자리}/
                    question_dir = (
                        image_output_dir / 
                        certification_id / 
                        company_id / 
                        round_subject_id / 
                        f"{question_no:03d}"
                    )
                    question_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 파일명: question-1.jpg, option1-1.jpg 등
                    image_filename = f"{slot_name}-{slot_idx}{image_suffix}"
                    image_path = question_dir / image_filename
                else:
                    # 과목 정보가 없으면 unknown 폴더에 저장
                    unknown_dir = image_output_dir / "unknown"
                    unknown_dir.mkdir(parents=True, exist_ok=True)
                    # 파일명에 PDF 파일명, 페이지, 문제번호 포함
                    base_name = pdf_filename.replace(".pdf", "") if pdf_filename else "unknown"
                    image_filename = f"{base_name}_page{page_index:03d}_q{question_no:03d}_img{image_index:02d}{image_suffix}"
                    image_path = unknown_dir / image_filename
            else:
                # 문제 번호를 찾을 수 없거나 메타데이터가 없는 경우 unknown 폴더에 저장
                unknown_dir = image_output_dir / "unknown"
                unknown_dir.mkdir(parents=True, exist_ok=True)
                base_name = pdf_filename.replace(".pdf", "") if pdf_filename else "unknown"
                image_filename = f"{base_name}_page{page_index:03d}_img{image_index:02d}{image_suffix}"
                image_path = unknown_dir / image_filename
            
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


def _build_page_questions_map(raw_text: str) -> dict[int, list[int]]:
    """페이지별 문제 번호 목록을 생성합니다."""
    PAGE_MARKER_PATTERN = re.compile(r"\[PAGE\s+(?P<page>\d+)\]")
    QUESTION_NUMBER_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\.\s")
    
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

