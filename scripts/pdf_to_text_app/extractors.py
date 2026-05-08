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
        try:
            page_images = list(page.images)
        except Exception:
            # 일부 PDF는 이미지 객체 파싱 도중 pypdf 내부 assertion이 발생할 수 있다.
            # 이 경우 해당 페이지 이미지는 건너뛰고 나머지 처리를 계속 진행한다.
            continue
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

