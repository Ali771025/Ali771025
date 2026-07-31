from __future__ import annotations

import hashlib
import re
from typing import Any

SQL_TABLE_RE = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([\[\]\w\.]+)", re.IGNORECASE)
SQL_COLUMN_RE = re.compile(r"\b([\[\]\w]+)\s+(?:INT|BIGINT|NVARCHAR|VARCHAR|DATETIME|DATE|BIT|DECIMAL|NUMERIC)", re.IGNORECASE)
FORBIDDEN_RE = re.compile(r"\b(DROP|TRUNCATE|DELETE|UPDATE|INSERT|ALTER|EXEC|MERGE)\b", re.IGNORECASE)


def checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def detect_document_type(content: str, declared_type: str) -> str:
    lowered = content.lower()
    if "create table" in lowered or "foreign key" in lowered:
        return "ddl"
    if "select" in lowered and "from" in lowered:
        return "approved_query" if declared_type != "gold_test" else "gold_test"
    if "join" in lowered:
        return "join_path"
    return declared_type


def extract_metadata(content: str) -> dict[str, Any]:
    tables = sorted({match.group(1).strip("[]") for match in SQL_TABLE_RE.finditer(content)})
    columns = sorted({match.group(1).strip("[]") for match in SQL_COLUMN_RE.finditer(content)})
    forbidden = sorted({match.group(1).upper() for match in FORBIDDEN_RE.finditer(content)})
    return {"tables": tables, "columns": columns, "forbidden_operations": forbidden}


def validate_knowledge(content: str, document_type: str) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    metadata = extract_metadata(content)

    if len(content.strip()) < 10:
        errors.append({"code": "EMPTY_OR_TOO_SHORT", "message": "محتوای سند بسیار کوتاه است."})
    if document_type in {"ddl", "schema"} and not metadata["tables"]:
        warnings.append({"code": "NO_TABLE_DETECTED", "message": "جدولی در سند شناسایی نشد."})
    if metadata["forbidden_operations"] and document_type != "forbidden_pattern":
        warnings.append(
            {
                "code": "FORBIDDEN_KEYWORD_PRESENT",
                "message": "کلمات حساس SQL در سند وجود دارد و نیازمند بازبینی است.",
                "keywords": metadata["forbidden_operations"],
            }
        )

    score = 1.0
    score -= 0.3 * len(errors)
    score -= 0.1 * len(warnings)
    return max(score, 0.0), errors, warnings
