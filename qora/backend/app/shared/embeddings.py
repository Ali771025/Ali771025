"""Deterministic hashed bag-of-words embeddings [TECH].

Placeholder for pgvector semantic embeddings (Phase 3+). Deterministic → testable,
no model downloads. Cosine similarity is used by duplicate detection and knowledge search.
"""
import hashlib
import math
import re

DIM = 128


def embed_text(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h >> 8) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 5) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return round(dot / (na * nb), 4)
