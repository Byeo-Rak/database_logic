from __future__ import annotations

import re


def clean_question_text(raw_text: str) -> str:
    lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[PAGE "):
            continue
        if "전자문제집 CBT : www.comcbt.com" in stripped:
            continue
        if stripped.startswith("최강 자격증 기출문제"):
            continue
        lines.append(stripped)
    text = " ".join(lines)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # PDF 추출 과정에서 숫자가 붙는 경우(예: 10129., 379.)를 분리해 문제 번호 인식을 돕는다.
    text = re.sub(r"(?<=\d{2})(?=(\d{2}\.\s))", " ", text)
    text = re.sub(r"([④❹]\s*\d)(\d{2}\.\s)", r"\1 \2", text)
    return text


def extract_subject_map(raw_text: str) -> dict[int, str]:
    subject_map: dict[int, str] = {}
    for match in re.finditer(r"(\d+)\s*과목\s*:\s*([^\n\r]+)", raw_text):
        index = int(match.group(1))
        name = match.group(2).strip()
        if index not in subject_map:
            subject_map[index] = name
    return subject_map


def normalize_compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_questions_from_text(raw_text: str) -> list[dict[str, str]]:
    cleaned = clean_question_text(raw_text)
    subject_map = extract_subject_map(raw_text)
    question_pattern = re.compile(r"(?<!\d)(\d{1,3})\.\s*(.*?)(?=(?<!\d)(\d{1,3})\.\s|$)")
    option_pattern = re.compile(
        r"[①❶]\s*(.*?)\s*[②❷]\s*(.*?)\s*[③❸]\s*(.*?)\s*[④❹]\s*(.*)",
        re.DOTALL,
    )

    questions: list[dict[str, str]] = []
    for question_match in question_pattern.finditer(cleaned):
        number = int(question_match.group(1))
        body = normalize_compact(question_match.group(2))

        if number < 1 or number > 150:
            continue

        option_match = option_pattern.search(body)
        if option_match:
            stem = normalize_compact(body[: option_match.start()])
            options = [normalize_compact(option_match.group(i)) for i in range(1, 5)]
        else:
            stem = body
            options = ["", "", "", ""]

        answer = ""
        for idx, marker in enumerate(("❶", "❷", "❸", "❹"), start=1):
            if marker in body:
                answer = str(idx)
                break

        subject_idx = ((number - 1) // 20) + 1
        subject_name = subject_map.get(subject_idx, f"{subject_idx}과목")
        questions.append(
            {
                "번호": str(number),
                "질문": stem,
                "문항1": options[0],
                "문항2": options[1],
                "문항3": options[2],
                "문항4": options[3],
                "정답": answer,
                "과목": subject_name,
            }
        )

    deduped_by_number: dict[int, dict[str, str]] = {}
    for row in questions:
        q_number = int(row["번호"])
        if q_number not in deduped_by_number:
            deduped_by_number[q_number] = row

    sorted_numbers = sorted(deduped_by_number)
    if not sorted_numbers:
        return []

    under_100 = [number for number in sorted_numbers if number <= 100]
    if under_100:
        max_reasonable = max(under_100)
    else:
        max_reasonable = max(sorted_numbers)
    filtered = [
        deduped_by_number[number] for number in sorted_numbers if number <= max_reasonable
    ]
    return filtered

