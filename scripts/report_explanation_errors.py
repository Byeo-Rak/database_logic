#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from target_exam_files import TARGET_PDF_FILES, pdf_to_excel_path  # pyright: ignore[reportMissingImports]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="해설 생성 실패/오답 시도 상세 리포트를 CSV로 생성합니다."
    )
    parser.add_argument(
        "--excel",
        default="",
        help="대상 Excel 파일 경로 (생략 시 코드의 TARGET_PDF_FILES 전체 대상)",
    )
    parser.add_argument(
        "--attempt-log",
        default="",
        help=(
            "해설 생성 시도 로그 JSONL 경로 (기본: "
            "output/explanation_logs/{excel_stem}.jsonl)"
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "출력 CSV 경로 (기본: "
            "output/explanation_logs/{excel_stem}_error_report.csv)"
        ),
    )
    parser.add_argument(
        "--from-target-files",
        action="store_true",
        help="(호환 옵션) 코드에 정의된 TARGET_PDF_FILES 목록의 Excel을 일괄 처리합니다.",
    )
    return parser.parse_args()


def resolve_excel_targets(args: argparse.Namespace, project_root: Path) -> list[Path]:
    if args.excel:
        return [Path(args.excel).expanduser().resolve()]
    output_root = project_root / "output"
    return [pdf_to_excel_path(pdf, output_root).resolve() for pdf in TARGET_PDF_FILES]


def process_excel(args: argparse.Namespace, excel_path: Path) -> int:
    if not excel_path.exists():
        print(f"⚠️  Excel 파일 없음: {excel_path}")
        return 0

    default_log = excel_path.parent.parent / "explanation_logs" / f"{excel_path.stem}.jsonl"
    attempt_log_path = (
        Path(args.attempt_log).expanduser().resolve()
        if args.attempt_log
        else default_log.resolve()
    )
    if not attempt_log_path.exists():
        print(f"⚠️  시도 로그 없음: {attempt_log_path}")
        return 0

    default_output = (
        attempt_log_path.parent / f"{excel_path.stem}_error_report.csv"
    ).resolve()
    output_path = (
        Path(args.output).expanduser().resolve() if args.output else default_output
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    failed_rows: list[dict[str, str]] = []
    total_records = 0

    with attempt_log_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            total_records += 1
            record = json.loads(line)
            if record.get("성공여부", False):
                continue

            attempts = record.get("attempts", [])
            for attempt in attempts:
                failed_rows.append(
                    {
                        "번호": str(record.get("번호", "")),
                        "행번호": str(record.get("row", "")),
                        "정답": str(record.get("정답", "")),
                        "시도횟수": str(attempt.get("attempt", "")),
                        "예측답": str(attempt.get("predicted_answer", "")),
                        "정답일치": str(attempt.get("is_correct", False)),
                        "해설초안": str(attempt.get("explanation", "")),
                        "오류": str(attempt.get("error", "")),
                    }
                )

    with output_path.open("w", encoding="utf-8", newline="") as csv_fp:
        writer = csv.DictWriter(
            csv_fp,
            fieldnames=[
                "번호",
                "행번호",
                "정답",
                "시도횟수",
                "예측답",
                "정답일치",
                "해설초안",
                "오류",
            ],
        )
        writer.writeheader()
        writer.writerows(failed_rows)

    print("-" * 80)
    print(f"입력 Excel: {excel_path}")
    print(f"입력 시도로그: {attempt_log_path}")
    print(f"총 기록 수: {total_records}")
    print(f"오답/실패 시도 수: {len(failed_rows)}")
    print(f"CSV 저장 완료: {output_path}")
    return 0


def main() -> int:
    args = parse_args()
    project_root = Path(".").resolve()
    excel_targets = resolve_excel_targets(args, project_root)

    print("=" * 80)
    print("오답 해설 리포트 생성 시작")
    print(f"대상 파일 수: {len(excel_targets)}")
    print("=" * 80)

    success_files = 0
    fail_files = 0
    for excel_path in excel_targets:
        try:
            exit_code = process_excel(args=args, excel_path=excel_path)
            if exit_code == 0:
                success_files += 1
            else:
                fail_files += 1
        except Exception as exc:  # noqa: BLE001
            fail_files += 1
            print(f"❌ 처리 실패: {excel_path}")
            print(f"   사유: {exc}")

    print("=" * 80)
    print("오답 해설 리포트 생성 종료")
    print(f"성공 파일: {success_files}")
    print(f"실패 파일: {fail_files}")
    print("=" * 80)
    return 0 if fail_files == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
