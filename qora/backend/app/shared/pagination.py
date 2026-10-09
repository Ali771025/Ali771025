"""Cursor pagination helper (API_CONTRACT §0)."""
import base64
import json
from typing import Any


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(json.loads(base64.urlsafe_b64decode(cursor.encode()))["o"])
    except Exception:
        return 0


def paginate(items: list[Any], cursor: str | None, limit: int) -> dict:
    off = decode_cursor(cursor)
    page = items[off : off + limit]
    nxt = off + limit if off + limit < len(items) else None
    return {"items": page, "next_cursor": encode_cursor(nxt) if nxt is not None else None}
