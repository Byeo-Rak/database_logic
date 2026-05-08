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
- `question_validation.log`: 기대 문제 수 대비 누락 문항 번호 로그(JSON Lines)

누락 파일만 자동 재처리 + 재검증:

```bash
python3 scripts/reprocess_validation_failures.py
```

위 스크립트는 `question_validation.log`에 있는 PDF만 다시 처리한 뒤, 여전히 누락된 파일만 로그에 다시 남깁니다.

## 참고

- 현재 스크립트는 텍스트 레이어가 있는 PDF를 대상으로 합니다.
- 스캔 이미지 PDF라면 OCR 단계(`pytesseract`, `ocrmypdf` 등)를 별도로 붙여야 합니다.

## 코드 구조

- `scripts/pdf_to_text.py`: 실행 엔트리포인트
- `scripts/pdf_to_text_app/cli.py`: CLI 인자 파싱
- `scripts/pdf_to_text_app/pipeline.py`: 전체 처리 흐름 오케스트레이션
- `scripts/pdf_to_text_app/extractors.py`: PDF 텍스트/이미지 추출
- `scripts/pdf_to_text_app/question_parser.py`: 문제/선지 파싱
- `scripts/pdf_to_text_app/writers.py`: CSV/XLSX/manifest 쓰기
- `scripts/pdf_to_text_app/paths.py`: 경로/메타데이터 유틸
- `scripts/pdf_to_text_app/models.py`: 공용 데이터 모델 및 상수

## Firebase 업로드

Firestore + Storage로 업로드하려면 서비스 계정 인증이 필요합니다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
python3 scripts/upload_to_firebase.py --year 2021 --rounds 1,2,3 --subject-key "정처기" --company-key "CBT"
```

환경변수 없이 바로 실행하려면, 아래 파일명 중 하나로 서비스 계정 키를 두면 자동 인식됩니다.

- `service-account.json`
- `serviceAccountKey.json`
- `firebase-service-account.json`
- `secrets/service-account.json`
- `secrets/serviceAccountKey.json`
- `secrets/firebase-service-account.json`

Firebase 업로드는 `.csv`가 아니라 `.xlsx`를 읽습니다. 엑셀에서 수정한 내용이 그대로 반영됩니다.
엑셀에는 아래 이미지 개수 컬럼이 포함됩니다.

- `문제이미지`
- `문항1이미지`
- `문항2이미지`
- `문항3이미지`
- `문항4이미지`

- Firestore 경로:
  - `subjects/{subjectKey}` 문서에 `companyList` 맵 저장
  - `subjects/{subjectKey}/companies/{companyKey}` 문서에 `roundList`, `questionSetList` 저장
  - `subjects/{subjectKey}/companies/{companyKey}/questionSets/{year-round-과목}` 문서에 문제 저장
- 각 `questionSets` 문서 안에 `questions` 맵(`"001"`, `"002"` ...)
- 각 문제는 `question`, `option1`~`option4` 구조를 가지며, 각 항목별 `hasImage`(0/1), `imageUrls` 보유
- 이미지 경로: `{subjectKey}/{companyKey}/{year-round}/{과목}/{문항번호}/{파일명}`
- 실제 업로드 전 검증: `--dry-run`
- 기본값은 `2021년`, `1,2,3회차`, `PDF 자동생성 on`, `이미지 JPG 변환 on`입니다.
- 기본 동작을 끄려면 `--no-build-from-pdf --no-convert-images-to-jpg --no-pdf-skip-existing` 사용
