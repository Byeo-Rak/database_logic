from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CertificationMeta:
    certification_id: str
    certification_name: str


CERTIFICATION_MAP: dict[str, CertificationMeta] = {
    "정처기": CertificationMeta("InfoProcessEngineer", "정보처리기사"),
    "정보처리기사": CertificationMeta("InfoProcessEngineer", "정보처리기사"),
    "컴활1급": CertificationMeta("ComputSkillsLV1", "컴퓨터활용능력1급"),
    "컴퓨터활용능력1급": CertificationMeta("ComputSkillsLV1", "컴퓨터활용능력1급"),
    "컴활2급": CertificationMeta("ComputSkillsLV2", "컴퓨터활용능력2급"),
    "컴퓨터활용능력2급": CertificationMeta("ComputSkillsLV2", "컴퓨터활용능력2급"),
    "산업안전": CertificationMeta("IndustrySafetyEnginner", "산업안전기사"),
    "산업안전기사": CertificationMeta("IndustrySafetyEnginner", "산업안전기사"),
}


COURSE_ID_MAP: dict[str, dict[str, str]] = {
    "InfoProcessEngineer": {
        "소프트웨어 설계": "SoftwareDesign",
        "소프트웨어 개발": "SoftwareDev",
        "데이터베이스 구축": "DatabaseCons",
        "프로그래밍 언어 활용": "ProgramLangUtil",
        "정보시스템 구축관리": "InfoSystemConstManag",
    },
    "ComputSkillsLV1": {
        "컴퓨터 일반": "GenComp",
        "스프레드시트 일반": "GenSpread",
        "데이터베이스 일반": "GenDatabase",
    },
    "ComputSkillsLV2": {
        "컴퓨터 일반": "GenComp",
        "스프레드시트 일반": "GenSpread",
    },
    "IndustrySafetyEnginner": {
        "안전관리론": "SafetyManagTheory",
        "인간공학 및 시스템안전공학": "ErgSysSafetyEnginner",
        "기계위험방지기술": "MecHazPrevTechno",
        "전기위험방지기술": "ElecHazaPrevenTechno",
        "화학설비위험방지기술": "ChemFaciliHazPrevTechno",
    },
}


def sanitize_alnum_identifier(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return cleaned or "Unknown"


def resolve_certification_meta(subject_key: str) -> CertificationMeta:
    key = subject_key.strip()
    if key in CERTIFICATION_MAP:
        return CERTIFICATION_MAP[key]
    fallback_id = sanitize_alnum_identifier(key)
    return CertificationMeta(fallback_id, key)


def resolve_course_id(certification_id: str, course_name: str) -> str:
    mapped = COURSE_ID_MAP.get(certification_id, {}).get(course_name.strip())
    if mapped:
        return mapped
    return sanitize_alnum_identifier(course_name)

