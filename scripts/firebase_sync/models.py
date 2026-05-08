from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExamFileSet:
    stem: str
    date: str
    csv_path: Path
    excel_path: Path
    txt_path: Path
    image_dir: Path
    round_no: int
    round_id: str

