from __future__ import annotations

import re
from dataclasses import dataclass


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

