# PDF Text Extraction

국가자격시험 PDF를 텍스트 파일로 일괄 변환하고, 이후 DB 적재에 활용할 수 있도록 메타데이터 인덱스 JSON을 생성합니다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 실행

### 1. 하드코딩 방식 (권장)

`scripts/pdf_to_text.py` 파일 내 `TARGET_FILES` 리스트를 편집하여 처리할 파일을 선택합니다.

```python
TARGET_FILES = [
    # 처리할 파일만 주석 해제
    "실기 시험/정처기/정보처리기사20210307(교사용).pdf",
    # "실기 시험/산업안전/산업안전기사20210515(교사용).pdf",
]
```

실행:
```bash
python3 scripts/pdf_to_text.py
```

### 2. 출력 구조

- `output/text`: 페이지 구분자가 포함된 원문 `.txt`
- `output/csv`: 문제 구조화 결과 `.csv` (`번호`, `질문`, `문항1~4`, `정답`, `과목`)
- `output/excel`: 문제 구조화 결과 `.xlsx` (수동 편집 보존)
- `output/images`: Firebase Storage와 동일한 구조의 이미지 파일
  - `images/{certificationId}/{companyId}/{roundId-subjectId}/{questionNo}/question-1.jpg`
  - `images/unknown/`: 인식 실패한 이미지 (파일명에 위치 정보 포함)

예시:
```
output/images/InfoProcessEngineer/CBT/2021-1-SoftwareDesign/001/question-1.jpg
output/images/InfoProcessEngineer/CBT/2021-1-DatabaseCons/044/option1-1.png
output/images/unknown/산업안전기사20210515(교사용)_page001_q144_img04.jpg
output/excel/정처기/정보처리기사20210307(교사용).xlsx
```

## 주요 기능

### Excel 수동 편집 보존
스크립트를 다시 실행해도 Excel 파일의 수동 편집 내용이 보존됩니다.
- **보존**: `번호`, `질문`, `문항1~4`, `정답`, `과목`
- **자동 업데이트**: `문제이미지`, `문항1~4이미지` (이미지 개수)

### 문제 누락 검증
- 예상 문제 수와 실제 파싱된 문제 수를 비교
- 누락된 문제 번호를 `output/text/question_validation.log`에 기록
- 재처리: `python3 scripts/reprocess_validation_failures.py`

### Unknown 이미지 처리
과목 정보를 파싱하지 못한 이미지는 `output/images/unknown/` 폴더에 저장되며, 파일명에 위치 정보가 포함됩니다.
```
산업안전기사20210515(교사용)_page001_q144_img04.jpg
→ 파일: 산업안전기사20210515(교사용)
→ 페이지: 1
→ 인식된 문제번호: 144
→ 이미지 순서: 4번째
```

## 옵션 설정

`scripts/pdf_to_text.py` 파일 내 `OPTIONS` 딕셔너리:

```python
OPTIONS = {
    "convert_images_to_jpg": True,   # 이미지를 JPG로 변환
    "skip_existing": False,           # 기존 파일 건너뛰기
    "fail_fast": False,               # 첫 오류 시 중단
}
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
- `scripts/generate_explanations.py`: GPT 기반 해설 생성 + 정답 검증(최대 3회 시도)
- `scripts/report_explanation_errors.py`: 실패 문항의 오답 시도 해설 CSV 리포트 생성

## Firebase 업로드

Firestore + Storage로 업로드하려면 서비스 계정 인증이 필요합니다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
python3 scripts/upload_to_firebase.py --year 2021 --rounds 1,2,3 --subject-key "정처기" --company-key "CBT"
```

기본 전체 타깃 일괄 업로드:

```bash
python3 scripts/upload_to_firebase.py --all-default-targets
```

## GPT 해설 생성

Excel(`번호`,`질문`,`문항1~4`,`정답`)을 기반으로 GPT 해설을 생성합니다.

- 1차: 질문/문항만 전달해 답+해설 생성
- 검증: 생성한 답과 Excel `정답` 비교
- 불일치: 최대 2회 추가 시도(총 3회)
- 최종 실패: `해설` 컬럼에 `ai 해설 오류` 기록

```bash
python3 scripts/generate_explanations.py --excel "output/excel/정처기/정보처리기사20210307(교사용).xlsx"
```

`--excel`을 생략하면 `scripts/target_exam_files.py`의 `TARGET_PDF_FILES` 목록을 기준으로 전체 Excel을 자동 순회합니다.

```bash
python3 scripts/generate_explanations.py
```

실패 문항 오답 시도 리포트(CSV):

```bash
python3 scripts/report_explanation_errors.py --excel "output/excel/정처기/정보처리기사20210307(교사용).xlsx"
```

리포트도 `--excel` 생략 시 `TARGET_PDF_FILES` 기준 전체 자동 생성됩니다.

```bash
python3 scripts/report_explanation_errors.py
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
