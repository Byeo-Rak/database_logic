from __future__ import annotations

import argparse


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

