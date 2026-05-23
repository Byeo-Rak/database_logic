#!/usr/bin/env python3
"""
PDF 텍스트 추출 및 이미지 처리 스크립트

사용법:
1. 아래 TARGET_FILES 리스트에서 처리하고 싶은 PDF 파일만 활성화 (주석 해제)
2. 필요없는 파일은 주석 처리 (#)
3. 스크립트 실행: python scripts/pdf_to_text.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdf_to_text_app.pipeline import run  # pyright: ignore[reportMissingImports]
import argparse


# ============================================================
# 처리할 파일 목록 (필요한 것만 주석 해제)
# ============================================================
TARGET_FILES = [
    # ====== 정보처리기사 ======
    "실기 시험/정처기/정보처리기사20200606(교사용).pdf",  # 2020년 1회
    "실기 시험/정처기/정보처리기사20200822(교사용).pdf",  # 2020년 2회
    "실기 시험/정처기/정보처리기사20200926(교사용).pdf",  # 2020년 3회
    "실기 시험/정처기/정보처리기사20210307(교사용).pdf",  # 2021년 1회
    "실기 시험/정처기/정보처리기사20210515(교사용).pdf",  # 2021년 2회
    "실기 시험/정처기/정보처리기사20210814(교사용).pdf",  # 2021년 3회
    "실기 시험/정처기/정보처리기사20220305(교사용).pdf",  # 2022년 1회
    "실기 시험/정처기/정보처리기사20220424(교사용).pdf",  # 2022년 2회
    
    # ====== 산업안전기사 ======
    "실기 시험/산업안전/산업안전기사20200606(교사용).pdf",  # 2020년 1회
    "실기 시험/산업안전/산업안전기사20200822(교사용).pdf",  # 2020년 2회
    "실기 시험/산업안전/산업안전기사20200926(교사용).pdf",  # 2020년 3회
    "실기 시험/산업안전/산업안전기사20210307(교사용).pdf",  # 2021년 1회
    "실기 시험/산업안전/산업안전기사20210515(교사용).pdf",  # 2021년 2회
    "실기 시험/산업안전/산업안전기사20210814(교사용).pdf",  # 2021년 3회
    "실기 시험/산업안전/산업안전기사20220305(교사용).pdf",  # 2022년 1회
    "실기 시험/산업안전/산업안전기사20220424(교사용).pdf",  # 2022년 2회
    
    # ====== 컴퓨터활용능력 1급 ======
    "실기 시험/컴활1급/컴퓨터활용능력1급20160305(교사용).pdf",  # 2016년 1회
    "실기 시험/컴활1급/컴퓨터활용능력1급20160625(교사용).pdf",  # 2016년 2회
    "실기 시험/컴활1급/컴퓨터활용능력1급20161022(교사용).pdf",  # 2016년 3회
    "실기 시험/컴활1급/컴퓨터활용능력1급20170304(교사용).pdf",  # 2017년 1회
    "실기 시험/컴활1급/컴퓨터활용능력1급20170902(교사용).pdf",  # 2017년 2회
    "실기 시험/컴활1급/컴퓨터활용능력1급20180303(교사용).pdf",  # 2018년 1회
    "실기 시험/컴활1급/컴퓨터활용능력1급20180901(교사용).pdf",  # 2018년 2회
    "실기 시험/컴활1급/컴퓨터활용능력1급20190302(교사용).pdf",  # 2019년 1회
    "실기 시험/컴활1급/컴퓨터활용능력1급20190831(교사용).pdf",  # 2019년 2회
    "실기 시험/컴활1급/컴퓨터활용능력1급20200229(교사용).pdf",  # 2020년 1회
    "실기 시험/컴활1급/컴퓨터활용능력1급20200704(교사용).pdf",  # 2020년 2회
    
    # ====== 컴퓨터활용능력 2급 ======
    "실기 시험/컴활2급/컴퓨터활용능력2급20160305(교사용).pdf",  # 2016년 1회
    "실기 시험/컴활2급/컴퓨터활용능력2급20160625(교사용).pdf",  # 2016년 2회
    "실기 시험/컴활2급/컴퓨터활용능력2급20161022(교사용).pdf",  # 2016년 3회
    "실기 시험/컴활2급/컴퓨터활용능력2급20170304(교사용).pdf",  # 2017년 1회
    "실기 시험/컴활2급/컴퓨터활용능력2급20170902(교사용).pdf",  # 2017년 2회
    "실기 시험/컴활2급/컴퓨터활용능력2급20180303(교사용).pdf",  # 2018년 1회
    "실기 시험/컴활2급/컴퓨터활용능력2급20180901(교사용).pdf",  # 2018년 2회
    "실기 시험/컴활2급/컴퓨터활용능력2급20190302(교사용).pdf",  # 2019년 1회
    "실기 시험/컴활2급/컴퓨터활용능력2급20190831(교사용).pdf",  # 2019년 2회
    "실기 시험/컴활2급/컴퓨터활용능력2급20200229(교사용).pdf",  # 2020년 1회
    "실기 시험/컴활2급/컴퓨터활용능력2급20200704(교사용).pdf",  # 2020년 2회
]


# ============================================================
# 옵션 설정
# ============================================================
OPTIONS = {
    "convert_images_to_jpg": True,   # 이미지를 JPG로 변환
    "skip_existing": False,           # 기존 파일 건너뛰기 (False = 덮어쓰기)
    "fail_fast": False,               # 첫 오류 발생 시 중단
}


def main():
    # 활성화된 파일만 필터링 (주석 처리되지 않은 것)
    active_files = [f for f in TARGET_FILES if not f.strip().startswith("#") and f.strip()]
    
    if not active_files:
        print("❌ 처리할 파일이 없습니다.")
        print("   TARGET_FILES 리스트에서 파일의 주석(#)을 해제하세요.")
        return 1
    
    print(f"📋 처리할 파일 {len(active_files)}개:")
    for f in active_files:
        print(f"   - {f}")
    print()
    
    # 각 파일에 대해 처리
    success_count = 0
    error_count = 0
    
    for target_file in active_files:
        try:
            # 파일 경로 확인
            file_path = Path(target_file)
            if not file_path.exists():
                print(f"⚠️  파일을 찾을 수 없습니다: {target_file}")
                error_count += 1
                continue
            
            # argparse.Namespace 생성
            # target_file은 "실기 시험/정처기/파일명.pdf" 형식
            # input_dir은 "실기 시험"으로 고정
            # glob은 "정처기/파일명.pdf" 형식으로 변환
            relative_path = str(file_path.relative_to("실기 시험"))
            
            args = argparse.Namespace(
                input_dir="실기 시험",
                output_dir="output/text",
                excel_output_dir="output/excel",
                image_output_dir="output/images",
                convert_images_to_jpg=OPTIONS["convert_images_to_jpg"],
                manifest="output/text/manifest.json",
                glob=relative_path,  # "정처기/파일명.pdf"
                skip_existing=OPTIONS["skip_existing"],
                fail_fast=OPTIONS["fail_fast"],
            )
            
            # 처리 실행
            print(f"\n{'='*60}")
            print(f"처리 중: {target_file}")
            print(f"{'='*60}")
            result = run(args)
            
            if result == 0:
                success_count += 1
                print(f"✅ 완료: {target_file}")
            else:
                error_count += 1
                print(f"❌ 실패: {target_file}")
                
        except Exception as e:
            error_count += 1
            print(f"❌ 오류 발생: {target_file}")
            print(f"   {str(e)}")
    
    # 결과 요약
    print(f"\n{'='*60}")
    print(f"📊 처리 완료")
    print(f"{'='*60}")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {error_count}개")
    print(f"📁 총: {len(active_files)}개")
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
