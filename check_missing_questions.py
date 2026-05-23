#!/usr/bin/env python3
"""
Excel 파일에서 비어있는 문제 번호를 확인하는 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from pdf_to_text_app.question_parser import parse_questions_from_text  # pyright: ignore[reportMissingImports]
from target_exam_files import TARGET_PDF_FILES, get_subject_from_path  # pyright: ignore[reportMissingImports]


# 기대하는 문제 수
EXPECTED_QUESTION_COUNTS = {
    "정처기": 100,
    "산업안전": 120,
    "컴활1급": 60,
    "컴활2급": 40,
}


def check_missing_questions(txt_path: Path, expected_count: int) -> list[int]:
    """txt 파일을 파싱해서 누락된 문제 번호 반환"""
    if not txt_path.exists():
        return list(range(1, expected_count + 1))  # 파일이 없으면 모두 누락
    
    raw_text = txt_path.read_text(encoding="utf-8")
    questions = parse_questions_from_text(raw_text, expected_count=expected_count)
    
    # 비어있는 문제 찾기 (질문이 없는 경우)
    found_numbers = {int(q["번호"]) for q in questions if q.get("질문", "").strip()}
    missing = [n for n in range(1, expected_count + 1) if n not in found_numbers]
    
    return missing


def main():
    print("=" * 80)
    print("Excel 파일 누락 문제 번호 확인")
    print("=" * 80)
    print()
    
    total_files = 0
    total_missing = 0
    files_with_missing = []
    
    for pdf_path_str in TARGET_PDF_FILES:
        pdf_path = Path(pdf_path_str)
        subject = get_subject_from_path(pdf_path_str)
        expected_count = EXPECTED_QUESTION_COUNTS.get(subject, 100)
        
        # txt 파일 경로 생성
        txt_path = Path("output/text") / subject / pdf_path.with_suffix(".txt").name
        
        if not txt_path.exists():
            print(f"⚠️  파일 없음: {pdf_path.name}")
            continue
        
        total_files += 1
        
        # 누락된 문제 확인
        missing = check_missing_questions(txt_path, expected_count)
        
        if missing:
            total_missing += len(missing)
            files_with_missing.append((pdf_path.name, subject, missing))
            
            # 최대 20개까지만 표시
            missing_display = missing[:20]
            more = f" ...외 {len(missing) - 20}개" if len(missing) > 20 else ""
            
            print(f"❌ {pdf_path.name}")
            print(f"   과목: {subject} (기대: {expected_count}문제)")
            print(f"   누락: {len(missing)}개 - {missing_display}{more}")
            print()
        else:
            print(f"✅ {pdf_path.name} - 완벽 ({expected_count}/{expected_count})")
    
    # 요약
    print()
    print("=" * 80)
    print("요약")
    print("=" * 80)
    print(f"총 파일 수: {total_files}개")
    print(f"문제 있는 파일: {len(files_with_missing)}개")
    print(f"총 누락 문제 수: {total_missing}개")
    print()
    
    if files_with_missing:
        print("문제별 상세:")
        print("-" * 80)
        for filename, subject, missing in files_with_missing:
            print(f"\n{filename} ({subject}):")
            # 10개씩 끊어서 보기 좋게 출력
            for i in range(0, len(missing), 10):
                chunk = missing[i:i+10]
                print(f"  {chunk}")


if __name__ == "__main__":
    main()
