"""Knowledge pipeline: upload → safety scan → extract → normalize → chunk → embed → index.

The creator never sees these words in the UI [PRD] — only 'training material'.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.knowledge.models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeVersion,
)
from app.shared.embeddings import embed_text
from app.shared.errors import FORBIDDEN, NOT_FOUND, AppError

BLOCKED_WORDS = ["malware source code", "how to make a bomb", "child abuse", "stolen credit card"]
CHUNK_SIZE = 500


class KnowledgeService:
    # ---------- collections ----------
    @staticmethod
    def create_collection(db: Session, creator_id: int, name: str, description: str = "") -> KnowledgeCollection:
        c = KnowledgeCollection(creator_id=creator_id, name=name, description=description)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c

    @staticmethod
    def owned_collection(db: Session, collection_id: int, creator_id: int) -> KnowledgeCollection:
        c = db.get(KnowledgeCollection, collection_id)
        if not c:
            raise AppError(NOT_FOUND, "Collection not found", 404)
        if c.creator_id != creator_id:
            raise AppError(FORBIDDEN, "Not your collection", 403)
        return c

    @staticmethod
    def list_collections(db: Session, creator_id: int) -> list[KnowledgeCollection]:
        return list(db.scalars(select(KnowledgeCollection).where(KnowledgeCollection.creator_id == creator_id)).all())

    # ---------- ingestion pipeline ----------
    @staticmethod
    def add_source(db: Session, collection_id: int, creator_id: int, name: str, content: str,
                   source_date: datetime | None = None, freshness_policy: str = "stale_after_90d") -> KnowledgeSource:
        KnowledgeService.owned_collection(db, collection_id, creator_id)
        src = KnowledgeSource(
            collection_id=collection_id, name=name, scan_status="pending",
            source_date=source_date,
            last_verified_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
            freshness_policy=freshness_policy,
        )
        db.add(src)
        db.flush()

        # 1. safety scan
        low = content.lower()
        if any(w in low for w in BLOCKED_WORDS):
            src.scan_status = "blocked"
            db.commit()
            db.refresh(src)
            return src
        src.scan_status = "clean"

        # 2. extract + normalize
        text = " ".join(content.split())

        # 3. document
        doc = KnowledgeDocument(source_id=src.id, title=name, extracted_text=text,
                                size_bytes=len(text.encode()))
        db.add(doc)
        db.flush()

        # 4. chunk + embed + index
        for i in range(0, max(len(text), 1), CHUNK_SIZE):
            chunk_text = text[i : i + CHUNK_SIZE]
            if not chunk_text.strip():
                continue
            db.add(KnowledgeChunk(
                document_id=doc.id,
                seq=i // CHUNK_SIZE,
                content=chunk_text,
                embedding=embed_text(chunk_text),
                chunk_meta={"source": name},
            ))
        db.commit()
        db.refresh(src)
        return src

    # ---------- versions ----------
    @staticmethod
    def freeze_version(db: Session, collection_id: int, creator_id: int) -> KnowledgeVersion:
        coll = KnowledgeService.owned_collection(db, collection_id, creator_id)
        sources = db.scalars(select(KnowledgeSource).where(KnowledgeSource.collection_id == collection_id)).all()
        docs = []
        for s in sources:
            docs.extend(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == s.id)).all())
        chunk_count = 0
        for d in docs:
            chunk_count += len(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == d.id)).all())
        n = len(db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.collection_id == collection_id)).all()) + 1
        v = KnowledgeVersion(
            collection_id=collection_id,
            version_no=n,
            snapshot={"source_ids": [s.id for s in sources], "document_ids": [d.id for d in docs], "chunk_count": chunk_count},
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return v

    # ---------- retrieval (used by the runtime) ----------
    @staticmethod
    def search(db: Session, knowledge_version_id: int, query: str, k: int = 2) -> list[str]:
        v = db.get(KnowledgeVersion, knowledge_version_id)
        if not v:
            return []
        qvec = embed_text(query)
        from app.shared.embeddings import cosine

        scored = []
        for doc_id in v.snapshot.get("document_ids", []):
            for ch in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)).all():
                scored.append((cosine(qvec, ch.embedding or []), ch.content))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k] if _ > 0.05]

    # ---------- freshness: used by reputation and discovery ranking ----------
    FRESHNESS_DAYS = {"stale_after_30d": 30, "stale_after_90d": 90, "stale_after_180d": 180}

    @staticmethod
    def _source_is_fresh(src: KnowledgeSource, now: datetime | None = None) -> bool:
        if src.scan_status != "clean":
            return False
        policy = src.freshness_policy or "stale_after_90d"
        if policy == "never":
            return True
        now_naive = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
        cutoff = src.expires_at
        if cutoff is None:
            basis = src.last_verified_at or src.source_date or src.ingested_at
            if basis is None:
                return True
            days = KnowledgeService.FRESHNESS_DAYS.get(policy, 90)
            cutoff = basis + timedelta(days=days)
        return cutoff.replace(tzinfo=None) > now_naive

    @staticmethod
    def freshness_for_version(db: Session, knowledge_version_id: int | None) -> dict:
        """Return a bounded freshness signal without exposing source content to callers."""
        if not knowledge_version_id:
            return {"score": 0.75, "stale": False, "stale_sources": [], "fingerprint": "no-material"}
        version = db.get(KnowledgeVersion, int(knowledge_version_id))
        if not version:
            return {"score": 0.0, "stale": True, "stale_sources": ["missing-version"], "fingerprint": "missing-version"}
        ids = version.snapshot.get("source_ids", [])
        sources = [db.get(KnowledgeSource, int(source_id)) for source_id in ids]
        sources = [source for source in sources if source is not None and source.scan_status == "clean"]
        if not sources:
            # No usable material is neutral: absence is not staleness.
            return {"score": 0.75, "stale": False, "stale_sources": [], "fingerprint": "empty"}
        stale = [source for source in sources if not KnowledgeService._source_is_fresh(source)]
        fresh_count = len(sources) - len(stale)
        fingerprint_data = "|".join(
            f"{source.id}:{source.last_verified_at}:{source.expires_at}:{source.freshness_policy}"
            for source in stale
        )
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32] if stale else "fresh"
        return {
            "score": round(fresh_count / len(sources), 3),
            "stale": bool(stale),
            "stale_sources": [source.id for source in stale],
            "fingerprint": fingerprint,
        }

    @staticmethod
    def verify_source(db: Session, source_id: int, creator_id: int, actor_id: int | None = None) -> dict:
        src = db.get(KnowledgeSource, source_id)
        if not src:
            raise AppError(NOT_FOUND, "Source not found", 404)
        KnowledgeService.owned_collection(db, src.collection_id, creator_id)
        if src.scan_status != "clean":
            raise AppError(FORBIDDEN, "Only approved training material can be verified", 403)
        now = datetime.now(timezone.utc)
        src.last_verified_at = now
        days = KnowledgeService.FRESHNESS_DAYS.get(src.freshness_policy or "stale_after_90d")
        src.expires_at = now + timedelta(days=days) if days else None
        from app.shared.audit import record

        record(db, actor_id, "knowledge.source.verified", source_id, {"freshness_policy": src.freshness_policy})
        db.commit()
        db.refresh(src)

        # A creator re-verification can restore the freshness component for bound services.
        from app.modules.reputation.service import ReputationService
        from app.modules.service.service import ServiceRegistry

        bound_versions = db.scalars(
            select(KnowledgeVersion).where(KnowledgeVersion.collection_id == src.collection_id)
        ).all()
        for knowledge_version in bound_versions:
            freshness = KnowledgeService.freshness_for_version(db, knowledge_version.id)
            if freshness["stale"]:
                continue
            for target in ServiceRegistry.services_using_knowledge_version(db, knowledge_version.id):
                for subject_type, subject_id in (("service", target["service_id"]), ("creator", target["creator_id"])):
                    ReputationService.apply_event(
                        db,
                        subject_type,
                        subject_id,
                        "quality_update",
                        idempotency_key=(
                            f"freshness-verified:{target['service_id']}:{knowledge_version.id}:"
                            f"{src.last_verified_at.isoformat()}:{subject_type}:{subject_id}"
                        ),
                        meta={"freshness_score": freshness["score"], "source_id": source_id},
                    )
        return KnowledgeService.source_status(db, source_id)

    # ---------- status ----------
    @staticmethod
    def source_status(db: Session, source_id: int) -> dict:
        src = db.get(KnowledgeSource, source_id)
        if not src:
            raise AppError(NOT_FOUND, "Source not found", 404)
        fresh = KnowledgeService._source_is_fresh(src)
        return {
            "id": src.id,
            "name": src.name,
            "scan_status": src.scan_status,
            "source_date": src.source_date,
            "ingested_at": src.ingested_at,
            "last_verified_at": src.last_verified_at,
            "expires_at": src.expires_at,
            "freshness_policy": src.freshness_policy,
            "fresh": fresh,
        }

    @staticmethod
    def collection_detail(db: Session, collection_id: int, creator_id: int) -> dict:
        KnowledgeService.owned_collection(db, collection_id, creator_id)
        sources = db.scalars(select(KnowledgeSource).where(KnowledgeSource.collection_id == collection_id)).all()
        versions = db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.collection_id == collection_id)).all()
        return {
            "id": collection_id,
            "sources": [KnowledgeService.source_status(db, s.id) for s in sources],
            "versions": [{"id": v.id, "version_no": v.version_no, "snapshot": v.snapshot, "created_at": v.created_at} for v in versions],
        }
