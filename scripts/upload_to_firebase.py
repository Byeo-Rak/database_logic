#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from firebase_sync.selector import (  # pyright: ignore[reportMissingImports]
    assign_images_to_questions,
    build_page_questions_map,
    detect_input_root,
    discover_exam_files,
    discover_target_pdfs,
    load_questions,
)
from firebase_sync.id_mapper import resolve_certification_meta  # pyright: ignore[reportMissingImports]
from firebase_sync.uploader import (  # pyright: ignore[reportMissingImports]
    init_firebase_app,
    upload_exam_to_firebase,
)
from pdf_to_text_app.pipeline import run as run_pdf_pipeline  # pyright: ignore[reportMissingImports]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload parsed exam data to Firestore and Firebase Storage."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root path (defaults to current directory).",
    )
    parser.add_argument(
        "--subject-key",
        default="정처기",
        help="Source subject key (Korean folder/category). e.g., 정처기",
    )
    parser.add_argument(
        "--company-key",
        default="CBT",
        help="Company id/name under subject. e.g., CBT",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Target exam year. Default: 2021",
    )
    parser.add_argument(
        "--rounds",
        default="1,2,3",
        help="Comma-separated rounds to upload. Example: 1,2,3",
    )
    parser.add_argument(
        "--storage-bucket",
        default="byeo-rak.firebasestorage.app",
        help="Firebase Storage bucket name.",
    )
    parser.add_argument(
        "--service-account",
        default="",
        help="Path to Firebase service-account JSON. If omitted, auto-detected.",
    )
    parser.add_argument(
        "--exam-prefix",
        default="정보처리기사",
        help="Target exam file prefix in PDF names.",
    )
    parser.add_argument(
        "--build-from-pdf",
        action="store_true",
        help="If CSV is missing, generate from PDF first. (default: on)",
    )
    parser.add_argument(
        "--no-build-from-pdf",
        dest="build_from_pdf",
        action="store_false",
        help="Disable PDF fallback generation.",
    )
    parser.add_argument(
        "--pdf-skip-existing",
        action="store_true",
        help="When building from PDF, skip outputs that already exist. (default: on)",
    )
    parser.add_argument(
        "--no-pdf-skip-existing",
        dest="pdf_skip_existing",
        action="store_false",
        help="Rebuild outputs even if they already exist.",
    )
    parser.add_argument(
        "--convert-images-to-jpg",
        action="store_true",
        help="When building from PDF, also save JPG images. (default: on)",
    )
    parser.add_argument(
        "--no-convert-images-to-jpg",
        dest="convert_images_to_jpg",
        action="store_false",
        help="Do not create JPG copies from extracted images.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except actual Firebase write/upload.",
    )
    parser.set_defaults(
        build_from_pdf=True,
        pdf_skip_existing=True,
        convert_images_to_jpg=True,
    )
    return parser.parse_args()


def parse_rounds(value: str) -> set[int]:
    rounds: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        rounds.add(int(token))
    if not rounds:
        raise ValueError("회차 값이 비어 있습니다. 예: --rounds 1,2,3")
    return rounds


def resolve_service_account_path(project_root: Path, provided_path: str) -> Path | None:
    if provided_path.strip():
        path = Path(provided_path).expanduser()
        if not path.is_absolute():
            path = (project_root / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"서비스 계정 키 파일을 찾지 못했습니다: {path}")
        return path

    candidates = [
        project_root / "service-account.json",
        project_root / "serviceAccountKey.json",
        project_root / "firebase-service-account.json",
        project_root / "secrets" / "service-account.json",
        project_root / "secrets" / "serviceAccountKey.json",
        project_root / "secrets" / "firebase-service-account.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def main() -> int:
    try:
        args = parse_args()
        project_root = Path(args.project_root).expanduser().resolve()
        rounds = parse_rounds(args.rounds)
        certification_meta = resolve_certification_meta(args.subject_key)
        service_account_path = resolve_service_account_path(
            project_root=project_root,
            provided_path=args.service_account,
        )

        try:
            file_sets = discover_exam_files(
                project_root=project_root,
                subject_key=args.subject_key,
                year=args.year,
                rounds=rounds,
            )
        except (ValueError, FileNotFoundError) as exc:
            if not args.build_from_pdf:
                raise
            print(f"[INFO] {exc}")
            print("[INFO] CSV가 없어 PDF에서 먼저 생성합니다.")
            input_root = detect_input_root(project_root)
            target_pdfs = discover_target_pdfs(
                project_root=project_root,
                year=args.year,
                rounds=rounds,
                exam_prefix=args.exam_prefix,
            )
            for round_no, date, pdf_path in target_pdfs:
                pipeline_args = argparse.Namespace(
                    input_dir=str(input_root),
                    output_dir=str(project_root / "output" / "text"),
                    csv_output_dir=str(project_root / "output" / "csv"),
                    excel_output_dir=str(project_root / "output" / "excel"),
                    image_output_dir=str(project_root / "output" / "images"),
                    manifest=str(project_root / "output" / "text" / "manifest.json"),
                    glob=pdf_path.name,
                    skip_existing=args.pdf_skip_existing,
                    fail_fast=True,
                    convert_images_to_jpg=args.convert_images_to_jpg,
                )
                build_exit_code = run_pdf_pipeline(pipeline_args)
                if build_exit_code != 0:
                    raise RuntimeError(
                        f"PDF 전처리 실패: round={round_no}, date={date}, file={pdf_path.name}"
                    )
            file_sets = discover_exam_files(
                project_root=project_root,
                subject_key=args.subject_key,
                year=args.year,
                rounds=rounds,
            )

        _, db, bucket = init_firebase_app(
            storage_bucket=args.storage_bucket,
            dry_run=args.dry_run,
            service_account_path=service_account_path,
        )

        total_questions = 0
        total_images = 0
        for exam in file_sets:
            questions = load_questions(exam.excel_path)
            page_questions_map = build_page_questions_map(exam.txt_path)
            question_images, unassigned_images = assign_images_to_questions(
                image_dir=exam.image_dir,
                page_questions_map=page_questions_map,
            )
            stats = upload_exam_to_firebase(
                db=db,
                bucket=bucket,
                exam=exam,
                questions=questions,
                question_images=question_images,
                unassigned_images=unassigned_images,
                certification_id=certification_meta.certification_id,
                certification_name=certification_meta.certification_name,
                company_key=args.company_key,
                dry_run=args.dry_run,
            )
            total_questions += stats["questions"]
            total_images += stats["images"]
            print(
                f"[OK] {exam.stem} round={exam.round_id} "
                f"questions={stats['questions']} images={stats['images']}"
            )

        print(
            "Completed firebase sync: "
            f"files={len(file_sets)}, questions={total_questions}, images={total_images}, "
            f"dry_run={args.dry_run}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        if (
            "default credentials were not found" in str(exc).lower()
            or "application default credentials" in str(exc).lower()
        ):
            print(
                "[ERROR] Firebase 인증키를 찾지 못했습니다. "
                "아래 경로 중 하나에 서비스 계정 JSON을 두거나 "
                "--service-account 옵션을 사용하세요:\n"
                "- ./service-account.json\n"
                "- ./serviceAccountKey.json\n"
                "- ./firebase-service-account.json\n"
                "- ./secrets/service-account.json\n"
                "- ./secrets/serviceAccountKey.json\n"
                "- ./secrets/firebase-service-account.json",
                file=sys.stderr,
            )
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

