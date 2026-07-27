from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .database import Database


STOPWORDS = {
    "از", "با", "به", "برای", "در", "را", "است", "باشد", "شود", "می", "چه",
    "طبق", "علت", "وضعیت", "اقدام", "سطح", "بالا", "بالایی", "رویه", "کلیدواژه",
    "the", "is", "a", "an", "of", "to", "for", "no", "what", "which",
}


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for character in text.casefold():
        if character.isalnum() or character == "_":
            current.append(character)
        elif current:
            token = "".join(current)
            if len(token) > 1 and token not in STOPWORDS:
                tokens.append(token)
            current = []
    if current:
        token = "".join(current)
        if len(token) > 1 and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


class Embedder(Protocol):
    model_name: str

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class Reranker(Protocol):
    model_name: str

    def scores(self, query: str, documents: list[str]) -> list[float]: ...


class HashingEmbedder:
    """Deterministic offline development fallback; not a production semantic model."""

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions
        self.model_name = f"hashing-dev-{dimensions}"

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in _tokens(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class SentenceTransformerEmbedder:
    def __init__(self, model_path: str = "Qwen/Qwen3-Embedding-0.6B") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install the RAG extra: pip install -e '.[rag]'") from exc
        self.model_name = model_path
        self._model = SentenceTransformer(model_path)

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        kwargs = {"normalize_embeddings": True}
        if query:
            kwargs["prompt_name"] = "query"
        vectors = self._model.encode(texts, **kwargs)
        return [[float(value) for value in vector] for vector in vectors]


class TokenOverlapReranker:
    """Offline development fallback; production uses Qwen3-Reranker."""

    model_name = "token-overlap-dev"

    def scores(self, query: str, documents: list[str]) -> list[float]:
        query_tokens = set(_tokens(query))
        return [
            len(query_tokens.intersection(_tokens(document))) / max(len(query_tokens), 1)
            for document in documents
        ]


class QwenCrossEncoderReranker:
    def __init__(self, model_path: str = "Qwen/Qwen3-Reranker-0.6B") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("Install the RAG extra: pip install -e '.[rag]'") from exc
        self.model_name = model_path
        self._model = CrossEncoder(model_path)

    def scores(self, query: str, documents: list[str]) -> list[float]:
        raw = self._model.predict([(query, document) for document in documents])
        return [float(value) for value in raw]


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    content: str
    section: str
    source_id: str
    title: str
    version: str
    checksum: str
    authority_status: str
    fused_score: float
    channels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RagResult:
    query_id: str
    query_text: str
    evidence: tuple[Evidence, ...]
    embedding_model: str


class KnowledgeStore:
    def __init__(self, database: Database, embedder: Embedder) -> None:
        self.database = database
        self.embedder = embedder

    def add_document(
        self,
        source_id: str,
        title: str,
        version: str,
        sections: list[tuple[str, str]],
        authority_status: str = "AUTHORITATIVE",
        created_at_ms: int | None = None,
    ) -> str:
        if authority_status not in {"AUTHORITATIVE", "REFERENCE", "UNTRUSTED"}:
            raise ValueError("invalid authority_status")
        now_ms = created_at_ms if created_at_ms is not None else int(time.time() * 1000)
        full_text = "\n".join(f"{section}\n{content}" for section, content in sections)
        checksum = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        existing = self.database.connection.execute(
            "SELECT document_id FROM knowledge_documents WHERE source_id=? AND version=? AND checksum=?",
            (source_id, version, checksum),
        ).fetchone()
        if existing:
            return str(existing[0])
        document_id = str(uuid4())
        retrieval_texts = [f"{section}\n{content}" for section, content in sections]
        embeddings = self.embedder.encode(retrieval_texts)
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_documents(
                    document_id, source_id, title, version, checksum, authority_status, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (document_id, source_id, title, version, checksum, authority_status, now_ms),
            )
            for (section, content), embedding in zip(sections, embeddings):
                chunk_id = str(uuid4())
                connection.execute(
                    """INSERT INTO knowledge_chunks(
                        chunk_id, document_id, section, content, embedding_json,
                        embedding_model, token_count, created_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id, document_id, section, content, _json(embedding),
                        self.embedder.model_name, len(_tokens(content)), now_ms,
                    ),
                )
                connection.execute(
                    "INSERT INTO knowledge_chunks_fts(chunk_id, content) VALUES (?, ?)",
                    (chunk_id, f"{section}\n{content}"),
                )
        return document_id

    def add_node(
        self,
        entity_key: str,
        entity_type: str,
        canonical_name: str,
        aliases: tuple[str, ...] = (),
        status: str = "CONFIRMED",
    ) -> str:
        existing = self.database.connection.execute(
            "SELECT node_id FROM knowledge_nodes WHERE entity_key=?", (entity_key,),
        ).fetchone()
        if existing:
            return str(existing[0])
        node_id = str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_nodes(
                    node_id, entity_key, entity_type, canonical_name, aliases_json, status, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (node_id, entity_key, entity_type, canonical_name, _json(aliases), status, int(time.time() * 1000)),
            )
        return node_id

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
        evidence_chunk_id: str,
        confidence: float = 1.0,
        status: str = "CONFIRMED",
    ) -> str:
        existing = self.database.connection.execute(
            """SELECT edge_id FROM knowledge_edges
               WHERE source_node_id=? AND target_node_id=? AND relation_type=? AND evidence_chunk_id=?""",
            (source_node_id, target_node_id, relation_type, evidence_chunk_id),
        ).fetchone()
        if existing:
            return str(existing[0])
        edge_id = str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_edges(
                    edge_id, source_node_id, target_node_id, relation_type,
                    evidence_chunk_id, confidence, status, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    edge_id, source_node_id, target_node_id, relation_type,
                    evidence_chunk_id, confidence, status, int(time.time() * 1000),
                ),
            )
        return edge_id

    def document_chunks(self, document_id: str) -> list[str]:
        return [str(row[0]) for row in self.database.connection.execute(
            "SELECT chunk_id FROM knowledge_chunks WHERE document_id=? ORDER BY created_at_ms, chunk_id", (document_id,)
        )]

    def lexical(self, query: str, limit: int) -> list[str]:
        tokens = _tokens(query)
        if not tokens:
            return []
        expression = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
        rows = self.database.connection.execute(
            """SELECT chunk_id, bm25(knowledge_chunks_fts) AS score
               FROM knowledge_chunks_fts WHERE knowledge_chunks_fts MATCH ?
               ORDER BY score LIMIT ?""",
            (expression, limit),
        )
        return [str(row[0]) for row in rows]

    def dense(self, query: str, limit: int) -> list[str]:
        query_vector = self.embedder.encode([query], query=True)[0]
        scored: list[tuple[float, str]] = []
        for row in self.database.connection.execute(
            "SELECT chunk_id, embedding_json, embedding_model FROM knowledge_chunks"
        ):
            if row[2] != self.embedder.model_name:
                continue
            score = _cosine(query_vector, json.loads(row[1]))
            scored.append((score, str(row[0])))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [chunk_id for _, chunk_id in scored[:limit]]

    def graph(self, query: str, limit: int, max_hops: int = 2) -> list[str]:
        query_tokens = _tokens(query)

        def contains_phrase(phrase_tokens: list[str]) -> bool:
            width = len(phrase_tokens)
            return bool(width) and any(
                query_tokens[index:index + width] == phrase_tokens
                for index in range(len(query_tokens) - width + 1)
            )

        seeds: list[str] = []
        for row in self.database.connection.execute(
            "SELECT node_id, canonical_name, aliases_json FROM knowledge_nodes WHERE status='CONFIRMED'"
        ):
            phrases = [str(row[1]), *json.loads(row[2])]
            if any(contains_phrase(_tokens(phrase)) for phrase in phrases):
                seeds.append(str(row[0]))
        seen = set(seeds)
        frontier = list(seeds)
        evidence: list[str] = []
        for _ in range(max_hops):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self.database.connection.execute(
                f"""SELECT source_node_id, target_node_id, evidence_chunk_id
                    FROM knowledge_edges
                    WHERE status='CONFIRMED' AND (source_node_id IN ({placeholders}) OR target_node_id IN ({placeholders}))
                    ORDER BY confidence DESC, edge_id""",
                (*frontier, *frontier),
            ).fetchall()
            next_frontier: list[str] = []
            for row in rows:
                evidence.append(str(row[2]))
                for node_id in (str(row[0]), str(row[1])):
                    if node_id not in seen:
                        seen.add(node_id)
                        next_frontier.append(node_id)
            frontier = next_frontier
        return list(dict.fromkeys(evidence))[:limit]

    def evidence(self, chunk_id: str, score: float, channels: tuple[str, ...]) -> Evidence:
        row = self.database.connection.execute(
            """SELECT c.chunk_id, c.content, c.section, d.source_id, d.title,
                      d.version, d.checksum, d.authority_status
               FROM knowledge_chunks c JOIN knowledge_documents d ON d.document_id=c.document_id
               WHERE c.chunk_id=?""",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise KeyError(chunk_id)
        return Evidence(
            chunk_id=str(row[0]), content=str(row[1]), section=str(row[2]),
            source_id=str(row[3]), title=str(row[4]), version=str(row[5]),
            checksum=str(row[6]), authority_status=str(row[7]),
            fused_score=score, channels=channels,
        )

    def persist_query(self, result: RagResult, config: dict[str, object], created_at_ms: int) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO rag_queries(
                    query_id, query_text, embedding_model, retrieval_config_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?)""",
                (result.query_id, result.query_text, result.embedding_model, _json(config), created_at_ms),
            )
            connection.executemany(
                """INSERT INTO rag_evidence(
                    query_id, rank_no, chunk_id, fused_score,
                    retrieval_channels_json, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        result.query_id, rank, evidence.chunk_id, evidence.fused_score,
                        _json(evidence.channels), _json({
                            "source_id": evidence.source_id,
                            "title": evidence.title,
                            "version": evidence.version,
                            "checksum": evidence.checksum,
                            "section": evidence.section,
                            "authority_status": evidence.authority_status,
                        }),
                    )
                    for rank, evidence in enumerate(result.evidence)
                ],
            )


class HybridRagEngine:
    def __init__(self, store: KnowledgeStore, rrf_k: int = 60, reranker: Reranker | None = None) -> None:
        self.store = store
        self.rrf_k = rrf_k
        self.reranker = reranker

    def query(self, query_text: str, limit: int = 5, candidate_limit: int = 20, persist: bool = True) -> RagResult:
        rankings = {
            "lexical": self.store.lexical(query_text, candidate_limit),
            "dense": self.store.dense(query_text, candidate_limit),
            "graph": self.store.graph(query_text, candidate_limit),
        }
        scores: dict[str, float] = {}
        channels: dict[str, set[str]] = {}
        for channel, ranking in rankings.items():
            for rank, chunk_id in enumerate(ranking):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
                channels.setdefault(chunk_id, set()).add(channel)
        rerank_limit = min(len(scores), max(limit * 3, limit))
        ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:rerank_limit]
        candidates = [
            self.store.evidence(chunk_id, scores[chunk_id], tuple(sorted(channels[chunk_id])))
            for chunk_id in ordered
        ]
        if self.reranker and candidates:
            rerank_scores = self.reranker.scores(query_text, [f"{item.section}\n{item.content}" for item in candidates])
            candidates = [
                replace(item, channels=tuple(sorted(set(item.channels) | {"rerank"})))
                for _, item in sorted(
                    zip(rerank_scores, candidates), key=lambda pair: (-pair[0], pair[1].chunk_id)
                )
            ]
        evidence = tuple(candidates[:limit])
        result = RagResult(str(uuid4()), query_text, evidence, self.store.embedder.model_name)
        if persist:
            self.store.persist_query(
                result,
                {
                    "rrf_k": self.rrf_k, "limit": limit, "candidate_limit": candidate_limit,
                    "channels": list(rankings),
                    "reranker": self.reranker.model_name if self.reranker else None,
                },
                int(time.time() * 1000),
            )
        return result
