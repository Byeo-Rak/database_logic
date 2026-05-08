# 최종 DB 저장 구조 (A안 적용)

이 문서는 현재 코드(`scripts/upload_to_firebase.py`, `scripts/firebase_sync/uploader.py`) 기준의 최종 Firebase 저장 구조입니다.

- 컬렉션/문서 ID: 영문 코드 사용
- 표시용 이름(`name`): 한글 저장
- 루트 컬렉션: `certifications`

## 1) Firestore

### 1-1. 인증 문서 (Certification)

- 경로: `certifications/{certificationId}`
- 예: `certifications/InfoProcessEngineer`

필드:

- `certificationId`: string (예: `InfoProcessEngineer`)
- `name`: string (예: `정보처리기사`)
- `subjectList`: string[] (영문 과목 ID 배열)
  - 예: `["SoftwareDesign", "SoftwareDev", "DatabaseCons"]`
- `subjectNameMap`: map (영문 과목 ID -> 한글 과목명)
  - 예: `{ "DatabaseCons": "데이터베이스 구축" }`
- `companyList`: map
  - 키: 회사 ID (`CBT`)
  - 값:
    - `companyName`: string (예: `CBT`)
    - `rounds`: string[] (예: `["2021-1","2021-2","2021-3"]`)
    - `questionSets`: string[] (예: `["2021-1-DatabaseCons"]`)
- `updatedAt`: ISO datetime string

### 1-2. 회사별 문제셋 컬렉션 (companies 컬렉션 없음)

- 경로: `certifications/{certificationId}/{companyId}`
- 예: `certifications/InfoProcessEngineer/CBT`

`{companyId}`는 컬렉션 이름이며, 하위 문서로 문제셋을 저장합니다.

### 1-3. 문제셋 문서

- 경로: `certifications/{certificationId}/{companyId}/{roundId-subjectId}`
- 문서 ID: `{roundId}-{subjectId}` (A안)
  - 예: `2021-1-DatabaseCons`

필드:

- `docId`: string
- `displayId`: string (현재 `docId`와 동일 포맷)
- `certificationId`: string
- `certificationName`: string (한글)
- `companyId`: string
- `roundId`: string (예: `2021-1`)
- `year`: number
- `round`: number
- `examDate`: string (예: `20210307`)
- `sourceStem`: string (예: `정보처리기사20210307(교사용)`)
- `course`: map
  - `id`: string (예: `DatabaseCons`)
  - `name`: string (예: `데이터베이스 구축`)
- `questionCount`: number
- `questions`: map
  - 키: `"001"`, `"002"` ... (문항 번호 3자리 문자열)
  - 값: 문항 payload
- `updatedAt`: ISO datetime string

### 1-4. questions map 내부 구조

`questions["001"]` 예시 필드:

- `number`: number
- `answer`: string
- `course`: map (`id`, `name`)
- `question`: map (`text`, `Image`)
- `option1`: map (`text`, `Image`)
- `option2`: map (`text`, `Image`)
- `option3`: map (`text`, `Image`)
- `option4`: map (`text`, `Image`)
- `updatedAt`: ISO datetime string

`Image`는 이미지 개수입니다. (예: 0, 1, 2 ...)

### 1-5. 미할당 이미지 메타

- 경로: `certifications/{certificationId}/{companyId}/_meta-unassigned-{roundId}`
- 예: `certifications/InfoProcessEngineer/CBT/_meta-unassigned-2021-1`

필드:

- `count`: number
- `items`: array (`storagePath`)
- `roundId`: string
- `updatedAt`: ISO datetime string

## 2) Firebase Storage

기본 이미지 경로:

- `certifications/{certificationId}/{companyId}/{roundId-subjectId}/{questionNo3자리}/{filename}`
- 예:
  - `certifications/InfoProcessEngineer/CBT/2021-1-DatabaseCons/031/question-1.jpg`
  - `certifications/InfoProcessEngineer/CBT/2021-1-DatabaseCons/031/question-2.jpg`
  - `certifications/InfoProcessEngineer/CBT/2021-1-DatabaseCons/031/option1-1.jpg`
  - `certifications/InfoProcessEngineer/CBT/2021-1-DatabaseCons/031/option1-2.jpg`

미할당 이미지:

- `certifications/{certificationId}/{companyId}/{roundId}/_unassigned/{filename}`

## 3) 이미지 슬롯 매핑(현재)

문항 단위로 연결된 이미지 순서 기준:

- 1번째 이미지 -> `question.imageUrls`
- 2~5번째 이미지 -> `option1~option4.imageUrls`
- 6번째 이후 -> 다시 `question.imageUrls`

현재는 PDF 좌표 기반이 아닌 순서 기반 매핑입니다.

