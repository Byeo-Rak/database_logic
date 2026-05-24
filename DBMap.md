# Firebase 데이터 구조 (Admin Page 개발용 참고)

> 이 문서는 새로운 대화창에서도 곧바로 데이터 구조를 파악할 수 있도록 작성된 참고 문서입니다.

---

## 1. Firestore 컬렉션 구조 (계층 요약)

```
certifications/                          ← 최상위 컬렉션
  {certificationId}/                     ← 자격증 문서 (e.g. "InfoProcessEngineer")
    CBT/                                 ← 서브컬렉션: 회사(기관)별 (현재 "CBT" 고정)
      {year}-{round}-{courseId}/         ← 서브문서: 문제 세트 (e.g. "2021-1-SoftwareDesign")
```

---

## 2. 자격증 문서 (`certifications/{certificationId}`)

**경로 예시:** `certifications/InfoProcessEngineer`

| 필드 | 타입 | 설명 |
|------|------|------|
| `certificationId` | string | 자격증 영문 ID |
| `name` | string | 자격증 한글명 |
| `subjectList` | string[] | 등록된 과목 ID 목록 |
| `subjectNameMap` | map | `{ courseId: courseName }` 한글 과목명 매핑 |
| `companyList` | map | 기관별 메타 (아래 구조 참고) |
| `updatedAt` | string | ISO 8601 타임스탬프 |

**`companyList` 내부 구조:**
```json
{
  "CBT": {
    "companyName": "CBT",
    "rounds": ["2021-1", "2021-2", "2021-3"],
    "questionSets": ["2021-1-SoftwareDesign", "2021-1-DatabaseCons", ...]
  }
}
```

---

## 3. 문제 세트 문서 (`certifications/{certificationId}/CBT/{docId}`)

**경로 예시:** `certifications/InfoProcessEngineer/CBT/2021-1-SoftwareDesign`

| 필드 | 타입 | 설명 |
|------|------|------|
| `docId` | string | 문서 ID (= `{roundId}-{courseId}`) |
| `displayId` | string | 동일 (표시용) |
| `certificationId` | string | 자격증 영문 ID |
| `certificationName` | string | 자격증 한글명 |
| `companyId` | string | 기관 ID (현재 `"CBT"`) |
| `roundId` | string | `"{year}-{round}"` (e.g. `"2021-1"`) |
| `year` | number | 시험 연도 |
| `round` | number | 회차 번호 |
| `examDate` | string | 시험일 (`"YYYYMMDD"`) |
| `sourceStem` | string | 원본 Excel 파일명 (확장자 제외) |
| `course` | map | `{ id: courseId, name: courseName }` |
| `questionCount` | number | 문제 수 |
| `questions` | map | `{ "001": {...}, "002": {...}, ... }` |
| `updatedAt` | string | ISO 8601 타임스탬프 |

---

## 4. 개별 문제 (`questions` 맵 내부)

**키:** 3자리 zero-padding 문자열 (e.g. `"001"`, `"042"`)

| 필드 | 타입 | 설명 | Admin 수정 대상 |
|------|------|------|----------------|
| `number` | number | 문제 번호 | |
| `question` | SlotPayload | 질문 본문 | ✅ |
| `option1` | SlotPayload | 선택지 1 | ✅ |
| `option2` | SlotPayload | 선택지 2 | ✅ |
| `option3` | SlotPayload | 선택지 3 | ✅ |
| `option4` | SlotPayload | 선택지 4 | ✅ |
| `answer` | string | 정답 (`"1"` ~ `"4"`) | ✅ |
| `explanation` | string | 해설 (GPT 생성 또는 수동) | ✅ |
| `course` | map | `{ id, name }` 과목 정보 | |
| `updatedAt` | string | ISO 8601 타임스탬프 | |

**SlotPayload 구조:**
```json
{
  "text": "문제 또는 선택지 텍스트",
  "Image": 0
}
```
> `Image` 는 해당 슬롯에 연결된 이미지 개수 (0이면 이미지 없음)

---

## 5. 자격증 ID / 과목 ID 매핑표

### 자격증 (certificationId)

| 한글 키 | certificationId | 한글명 |
|---------|----------------|--------|
| 정처기 | `InfoProcessEngineer` | 정보처리기사 |
| 컴활1급 | `ComputSkillsLV1` | 컴퓨터활용능력1급 |
| 컴활2급 | `ComputSkillsLV2` | 컴퓨터활용능력2급 |
| 산업안전 | `IndustrySafetyEnginner` | 산업안전기사 |

### 과목 (courseId)

**정보처리기사 (`InfoProcessEngineer`)**
| 과목명 | courseId |
|--------|----------|
| 소프트웨어 설계 | `SoftwareDesign` |
| 소프트웨어 개발 | `SoftwareDev` |
| 데이터베이스 구축 | `DatabaseCons` |
| 프로그래밍 언어 활용 | `ProgramLangUtil` |
| 정보시스템 구축관리 | `InfoSystemConstManag` |

**컴퓨터활용능력1급 (`ComputSkillsLV1`)**
| 과목명 | courseId |
|--------|----------|
| 컴퓨터 일반 | `GenComp` |
| 스프레드시트 일반 | `GenSpread` |
| 데이터베이스 일반 | `GenDatabase` |

**컴퓨터활용능력2급 (`ComputSkillsLV2`)**
| 과목명 | courseId |
|--------|----------|
| 컴퓨터 일반 | `GenComp` |
| 스프레드시트 일반 | `GenSpread` |

**산업안전기사 (`IndustrySafetyEnginner`)**
| 과목명 | courseId |
|--------|----------|
| 안전관리론 | `SafetyManagTheory` |
| 인간공학 및 시스템안전공학 | `ErgSysSafetyEnginner` |
| 기계위험방지기술 | `MecHazPrevTechno` |
| 전기위험방지기술 | `ElecHazaPrevenTechno` |
| 화학설비위험방지기술 | `ChemFaciliHazPrevTechno` |

---

## 6. Firebase Storage 이미지 경로 구조

```
certifications/{certificationId}/{companyId}/{questionSetId}/{questionNo:03d}/{slot}-{idx}.{ext}
```

**슬롯 종류:** `question`, `option1`, `option2`, `option3`, `option4`

**예시:**
```
certifications/InfoProcessEngineer/CBT/2021-1-SoftwareDesign/001/question-1.jpg
certifications/InfoProcessEngineer/CBT/2021-1-SoftwareDesign/001/option1-1.jpg
```

### Storage 업로드 실패 시 폴백 저장 위치

Firebase Storage에 정상적으로 저장되지 않을 경우, 이미지는 로컬 `output/images/` 디렉토리에 남아 있습니다. 로컬 경로는 Firebase Storage 경로와 동일한 구조를 따릅니다.

| 상황 | 저장 위치 |
|------|-----------|
| 정상 업로드 | Firebase Storage (`certifications/{certificationId}/...`) |
| 업로드 실패 (네트워크/권한 오류 등) | 로컬 `output/images/{certificationId}/{companyId}/{questionSetId}/{questionNo}/` |
| 과목 인식 실패로 경로 결정 불가 | 로컬 `output/images/unknown/` (파일명에 위치 정보 포함) |

**`output/images/unknown/` 파일명 규칙:**
```
{원본파일명}_page{페이지번호:03d}_q{인식된문제번호}_img{이미지순서:02d}.{ext}
예시: 산업안전기사20210515(교사용)_page001_q144_img04.jpg
```

> Firestore 문제 데이터(questions 맵)는 업로드 실패 시 `output/excel/{과목명}/` 내 `.xlsx` 파일에 보존됩니다. 재업로드 시 해당 엑셀 파일을 그대로 사용하면 됩니다.

---

## 7. Admin Page에서 수정할 Firestore 경로

문제 1개를 수정할 때의 정확한 쓰기 경로:

```
certifications/{certificationId}/CBT/{year}-{round}-{courseId}
  → 문서 내 questions.{questionNo:03d} 맵 필드를 merge 업데이트
```

**수정 예시 (JavaScript SDK 기준):**
```js
const docRef = db
  .collection("certifications")
  .doc("InfoProcessEngineer")
  .collection("CBT")
  .doc("2021-1-SoftwareDesign");

await docRef.set({
  questions: {
    "001": {
      "question": { text: "수정된 질문", Image: 0 },
      "answer": "3",
      "explanation": "수정된 해설",
      "updatedAt": new Date().toISOString(),
    }
  }
}, { merge: true });
```

---

## 8. 데이터 흐름 요약

```
PDF 파일
  ↓ scripts/pdf_to_text.py
output/excel/{subject}/*.xlsx   ← 번호, 질문, 문항1~4, 정답, 과목 컬럼
output/images/{certificationId}/{companyId}/{questionSetId}/{questionNo}/   ← 추출 이미지 (로컬 보관)
output/images/unknown/   ← 과목 인식 실패 이미지 (파일명에 위치 정보 포함)
  ↓ scripts/generate_explanations.py  (.env의 gpt_api_key 사용)
output/excel/{subject}/*.xlsx   ← 해설 컬럼 추가 (GPT 생성, 실패 시 "ai 해설 오류")
  ↓ scripts/upload_to_firebase.py
Firestore certifications/{...}/CBT/{...}  ← questions 맵으로 저장  [실패 시: output/excel/*.xlsx 보존]
Firebase Storage  ← 이미지 파일  [실패 시: output/images/ 로컬 폴더 보존]
```

> **업로드 실패 시 재시도:** `output/excel/`의 엑셀 파일과 `output/images/`의 이미지 파일이 그대로 남아 있으므로, 문제 원인 해결 후 `upload_to_firebase.py`를 재실행하면 됩니다.
