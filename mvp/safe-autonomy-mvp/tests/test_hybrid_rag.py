from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from safe_autonomy.database import Database
from safe_autonomy.hybrid_rag import HashingEmbedder, HybridRagEngine, KnowledgeStore, TokenOverlapReranker


class HybridRagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "rag.sqlite3")
        self.database.migrate()
        self.store = KnowledgeStore(self.database, HashingEmbedder(64))
        document_id = self.store.add_document(
            "SOP-1", "SOP ایمنی", "1.0",
            [
                ("ادراک", "YOLO به تنهایی فاصله ندارد و برای TTC به عمق و tracking نیاز دارد."),
                ("باتری", "در شارژ بحرانی پیشنهاد LAND و در ذخیره پیشنهاد RETURN صادر می شود."),
            ],
        )
        chunks = {
            row[1]: row[0]
            for row in self.database.connection.execute(
                "SELECT chunk_id, section FROM knowledge_chunks WHERE document_id=?", (document_id,)
            )
        }
        yolo = self.store.add_node("yolo", "COMPONENT", "YOLO")
        depth = self.store.add_node("depth", "SIGNAL", "Depth", ("عمق",))
        self.store.add_edge(yolo, depth, "REQUIRES", chunks["ادراک"])

    def tearDown(self) -> None:
        self.database.close()
        self.temp.cleanup()

    def test_dense_lexical_graph_and_rerank_are_fused(self) -> None:
        engine = HybridRagEngine(self.store, reranker=TokenOverlapReranker())
        result = engine.query("YOLO برای عمق و TTC به چه چیزی نیاز دارد؟", limit=2)
        self.assertEqual(result.evidence[0].section, "ادراک")
        self.assertIn("dense", result.evidence[0].channels)
        self.assertIn("lexical", result.evidence[0].channels)
        self.assertIn("graph", result.evidence[0].channels)
        self.assertIn("rerank", result.evidence[0].channels)
        self.assertEqual(
            self.database.connection.execute("SELECT COUNT(*) FROM rag_queries").fetchone()[0], 1
        )

    def test_document_ingestion_is_idempotent(self) -> None:
        first_count = self.database.connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
        self.store.add_document(
            "SOP-1", "SOP ایمنی", "1.0",
            [
                ("ادراک", "YOLO به تنهایی فاصله ندارد و برای TTC به عمق و tracking نیاز دارد."),
                ("باتری", "در شارژ بحرانی پیشنهاد LAND و در ذخیره پیشنهاد RETURN صادر می شود."),
            ],
        )
        second_count = self.database.connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
        self.assertEqual(first_count, second_count)


if __name__ == "__main__":
    unittest.main()

