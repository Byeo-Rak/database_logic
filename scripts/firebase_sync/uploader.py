from __future__ import annotations

import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path

from .id_mapper import resolve_course_id
from .models import ExamFileSet

# 새로운 Firebase Storage 스타일 이미지 경로 패턴
# 경로: images/{cert}/{company}/{round-subject}/{qno}/question-1.jpg
FIREBASE_IMAGE_PATH_PATTERN = re.compile(
    r"[/\\](?P<qno>\d{3})[/\\](?P<slot>question|option[1-4])-(?P<idx>\d+)"
)


def sanitize_path_segment(value: str) -> str:
    return (
        value.strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "")
        .replace(":", "_")
    )


def build_storage_path(
    certification_id: str,
    company_key: str,
    question_set_id: str,
    question_number: int,
    filename: str,
) -> str:
    return (
        f"certifications/{sanitize_path_segment(certification_id)}/"
        f"{sanitize_path_segment(company_key)}/"
        f"{sanitize_path_segment(question_set_id)}/"
        f"{question_number:03d}/"
        f"{filename}"
    )


def build_question_set_doc_id(round_id: str, course_id: str) -> str:
    return f"{round_id}-{sanitize_path_segment(course_id)}"


def split_image_paths_by_slot(image_paths: list[Path]) -> dict[str, list[Path]]:
    """이미지 경로를 슬롯별로 분류합니다.
    
    신규 형식(images/.../001/question-1.jpg)이 있으면 경로 기반으로 분류하고,
    구버전 형식은 순서 기반으로 분류합니다.
    """
    slot_paths = {
        "question": [],
        "option1": [],
        "option2": [],
        "option3": [],
        "option4": [],
    }
    if not image_paths:
        return slot_paths

    # 신규 형식 확인 (경로 기반)
    has_new_format = any(
        FIREBASE_IMAGE_PATH_PATTERN.search(str(path).replace("\\", "/")) 
        for path in image_paths
    )
    
    if has_new_format:
        # 경로 기반 분류
        for path in image_paths:
            path_str = str(path).replace("\\", "/")
            match = FIREBASE_IMAGE_PATH_PATTERN.search(path_str)
            if match:
                slot = match.group("slot")
                if slot in slot_paths:
                    slot_paths[slot].append(path)
        return slot_paths
    
    # 구버전: 순서 기반 분류
    if len(image_paths) == 1:
        slot_paths["question"] = image_paths
        return slot_paths

    # 텍스트 레이아웃 좌표 정보가 없어, 기본적으로 첫 이미지는 문제 본문에 매핑한다.
    slot_paths["question"].append(image_paths[0])
    option_keys = ["option1", "option2", "option3", "option4"]
    for idx, path in enumerate(image_paths[1:5]):
        slot_paths[option_keys[idx]].append(path)
    for extra in image_paths[5:]:
        slot_paths["question"].append(extra)
    return slot_paths


def build_slot_payload(text: str, image_count: int) -> dict[str, object]:
    return {
        "text": text,
        "Image": image_count,
    }


def parse_image_count_from_row(
    row: dict[str, str], key: str, fallback_count: int
) -> int:
    raw = row.get(key, "").strip()
    if not raw:
        return fallback_count
    try:
        parsed = int(float(raw))
    except ValueError:
        return fallback_count
    return parsed if parsed >= 0 else 0


def init_firebase_app(
    storage_bucket: str, dry_run: bool, service_account_path: Path | None = None
):
    if dry_run:
        return None, None, None

    import firebase_admin
    from firebase_admin import credentials, firestore, storage

    try:
        app = firebase_admin.get_app()
    except ValueError:
        if service_account_path is not None:
            cred = credentials.Certificate(str(service_account_path))
        else:
            cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket})

    db = firestore.client(app=app)
    bucket = storage.bucket(app=app)
    return app, db, bucket


def upload_image_to_storage(
    bucket,
    local_path: Path,
    remote_path: str,
    dry_run: bool,
) -> str:
    if dry_run:
        return remote_path

    blob = bucket.blob(remote_path)
    content_type, _ = mimetypes.guess_type(str(local_path))
    blob.cache_control = "public,max-age=3600"
    blob.upload_from_filename(
        str(local_path),
        content_type=content_type or "application/octet-stream",
    )
    return remote_path


def upload_exam_to_firebase(
    db,
    bucket,
    exam: ExamFileSet,
    questions: list[dict[str, str]],
    question_images: dict[int, list[Path]],
    unassigned_images: list[Path],
    certification_id: str,
    certification_name: str,
    company_key: str,
    dry_run: bool,
) -> dict[str, int]:
    now = datetime.now(timezone.utc).isoformat()
    uploaded_images = 0

    if not dry_run:
        from firebase_admin import firestore

        certification_ref = db.collection("certifications").document(certification_id)
        certification_ref.set(
            {
                "certificationId": certification_id,
                "name": certification_name,
                "updatedAt": now,
            },
            merge=True,
        )
    else:
        firestore = None
        certification_ref = None

    course_question_map: dict[str, dict[str, object]] = {}
    created_doc_ids: list[str] = []
    encountered_course_ids: set[str] = set()
    encountered_course_name_map: dict[str, str] = {}
    for row in questions:
        try:
            question_no = int(row.get("번호", "0"))
        except ValueError:
            continue
        if question_no <= 0:
            continue

        course_name = row.get("과목", "").strip() or "미분류"
        course_id = resolve_course_id(certification_id, course_name)
        question_set_id = build_question_set_doc_id(exam.round_id, course_id)
        local_images = question_images.get(question_no, [])
        slot_paths = split_image_paths_by_slot(local_images)
        for slot_name, paths in slot_paths.items():
            for idx, path in enumerate(paths, start=1):
                extension = path.suffix.lower() or ".bin"
                filename = f"{slot_name}-{idx}{extension}"
                remote_path = build_storage_path(
                    certification_id=certification_id,
                    company_key=company_key,
                    question_set_id=question_set_id,
                    question_number=question_no,
                    filename=filename,
                )
                upload_image_to_storage(
                    bucket=bucket,
                    local_path=path,
                    remote_path=remote_path,
                    dry_run=dry_run,
                )
                uploaded_images += 1

        question_payload = {
            "number": question_no,
            "question": build_slot_payload(
                row.get("질문", ""),
                parse_image_count_from_row(
                    row, "문제이미지", len(slot_paths["question"])
                ),
            ),
            "option1": build_slot_payload(
                row.get("문항1", ""),
                parse_image_count_from_row(
                    row, "문항1이미지", len(slot_paths["option1"])
                ),
            ),
            "option2": build_slot_payload(
                row.get("문항2", ""),
                parse_image_count_from_row(
                    row, "문항2이미지", len(slot_paths["option2"])
                ),
            ),
            "option3": build_slot_payload(
                row.get("문항3", ""),
                parse_image_count_from_row(
                    row, "문항3이미지", len(slot_paths["option3"])
                ),
            ),
            "option4": build_slot_payload(
                row.get("문항4", ""),
                parse_image_count_from_row(
                    row, "문항4이미지", len(slot_paths["option4"])
                ),
            ),
            "answer": row.get("정답", ""),
            "explanation": row.get("해설", "").strip(),
            "course": {"id": course_id, "name": course_name},
            "updatedAt": now,
        }

        course_key = sanitize_path_segment(course_id)
        if course_key not in course_question_map:
            course_question_map[course_key] = {
                "courseId": course_id,
                "courseName": course_name,
                "questions": {},
            }
        encountered_course_ids.add(course_id)
        encountered_course_name_map[course_id] = course_name
        questions_map = course_question_map[course_key]["questions"]
        if isinstance(questions_map, dict):
            questions_map[f"{question_no:03d}"] = question_payload

    if unassigned_images:
        orphan_records: list[str] = []
        for path in unassigned_images:
            remote_path = (
                f"certifications/{sanitize_path_segment(certification_id)}/"
                f"{sanitize_path_segment(company_key)}/"
                f"{sanitize_path_segment(exam.round_id)}/"
                f"_unassigned/"
                f"{path.name}"
            )
            orphan_records.append(
                upload_image_to_storage(
                    bucket=bucket,
                    local_path=path,
                    remote_path=remote_path,
                    dry_run=dry_run,
                )
            )
            uploaded_images += 1

        if not dry_run and certification_ref is not None:
            certification_ref.collection(company_key).document(
                f"_meta-unassigned-{exam.round_id}"
            ).set(
                {
                    "count": len(orphan_records),
                    "items": orphan_records,
                    "roundId": exam.round_id,
                    "updatedAt": now,
                },
                merge=True,
            )

    if not dry_run and certification_ref is not None:
        question_sets_ref = certification_ref.collection(company_key)
        for course_key, course_data in course_question_map.items():
            course_id = str(course_data["courseId"])
            course_name = str(course_data["courseName"])
            questions_map = course_data["questions"]
            question_count = len(questions_map) if isinstance(questions_map, dict) else 0
            doc_id = build_question_set_doc_id(exam.round_id, course_id)
            created_doc_ids.append(doc_id)
            question_sets_ref.document(doc_id).set(
                {
                    "docId": doc_id,
                    "displayId": f"{exam.round_id}-{course_id}",
                    "certificationId": certification_id,
                    "certificationName": certification_name,
                    "companyId": company_key,
                    "roundId": exam.round_id,
                    "year": int(exam.date[:4]),
                    "round": exam.round_no,
                    "examDate": exam.date,
                    "sourceStem": exam.stem,
                    "course": {"id": course_id, "name": course_name},
                    "questionCount": question_count,
                    "questions": questions_map,
                    "updatedAt": now,
                },
                merge=True,
            )

        if firestore is not None and created_doc_ids and certification_ref is not None:
            update_payload: dict[str, object] = {
                "updatedAt": now,
                "subjectList": firestore.ArrayUnion(sorted(encountered_course_ids)),
                f"companyList.{company_key}.companyName": company_key,
                f"companyList.{company_key}.rounds": firestore.ArrayUnion([exam.round_id]),
                f"companyList.{company_key}.questionSets": firestore.ArrayUnion(created_doc_ids),
            }
            for course_id, course_name in encountered_course_name_map.items():
                update_payload[f"subjectNameMap.{course_id}"] = course_name

            certification_ref.set(
                {
                    "certificationId": certification_id,
                    "name": certification_name,
                },
                merge=True,
            )
            certification_ref.set(update_payload, merge=True)

    return {"questions": len(questions), "images": uploaded_images}

