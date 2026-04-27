# PDF Text Extraction

국가자격시험 PDF를 텍스트 파일로 일괄 변환하고, 이후 DB 적재에 활용할 수 있도록 메타데이터 인덱스 JSON을 생성합니다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

기본값으로 `실기 시험` 폴더 아래의 모든 PDF를 찾아 아래 결과를 함께 생성합니다.

- `output/text`: 페이지 구분자가 포함된 원문 `.txt`
- `output/csv`: 문제 구조화 결과 `.csv` (`번호`, `질문`, `문항1`, `문항2`, `문항3`, `문항4`, `정답`, `과목`)
- `output/excel`: 문제 구조화 결과 `.xlsx` (Excel)
- `output/images`: PDF 내부 이미지 추출 파일 (웹 노출용)

```bash
python3 scripts/pdf_to_text.py
```

예시 출력:

- `output/text/정처기/정보처리기사20220424(교사용).txt`
- `output/csv/정처기/정보처리기사20220424(교사용).csv`
- `output/excel/정처기/정보처리기사20220424(교사용).xlsx`
- `output/images/정처기/정보처리기사20220424(교사용)/page_001_img_01.png`
- `output/text/산업안전/산업안전기사20220424(교사용).txt`
- `output/text/manifest.json`

## 옵션

```bash
python3 scripts/pdf_to_text.py --skip-existing
python3 scripts/pdf_to_text.py --input-dir "실기 시험" --output-dir "output/text"
python3 scripts/pdf_to_text.py --csv-output-dir "output/csv" --excel-output-dir "output/excel"
python3 scripts/pdf_to_text.py --image-output-dir "output/images"
python3 scripts/pdf_to_text.py --convert-images-to-jpg
python3 scripts/pdf_to_text.py --fail-fast
```

## 생성되는 데이터

- `.txt`: 페이지 구분자(`[PAGE n]`)가 포함된 원문 텍스트
- `.csv`: 시험 문제를 행 단위로 구조화한 데이터
- `.xlsx`: `.csv`와 동일한 구조를 가진 엑셀 파일
- `output/images/...`: 페이지별 추출 이미지(`page_###_img_##.<ext>`)
- `manifest.json`: 원본 PDF 경로, 출력 TXT 경로, 시험 분류, 시험명, 시험일자, 페이지 수, 상태 정보

## 참고

- 현재 스크립트는 텍스트 레이어가 있는 PDF를 대상으로 합니다.
- 스캔 이미지 PDF라면 OCR 단계(`pytesseract`, `ocrmypdf` 등)를 별도로 붙여야 합니다.
