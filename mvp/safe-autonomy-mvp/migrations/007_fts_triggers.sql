-- Trigger-based FTS synchronisation for knowledge_chunks.  Earlier
-- migrations created the `knowledge_chunks_fts` FTS5 table without content
-- tracking, so the application had to maintain it by hand.  These triggers
-- ensure that any INSERT/UPDATE/DELETE on `knowledge_chunks` -- whether from
-- the application or from future migrations -- is reflected into the FTS
-- index automatically.  The script is idempotent (DROP TRIGGER IF EXISTS).

DROP TRIGGER IF EXISTS knowledge_chunks_ai;
CREATE TRIGGER knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
    INSERT INTO knowledge_chunks_fts(chunk_id, content) VALUES (new.chunk_id, new.content);
END;

DROP TRIGGER IF EXISTS knowledge_chunks_au;
CREATE TRIGGER knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
    DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.chunk_id;
    INSERT INTO knowledge_chunks_fts(chunk_id, content) VALUES (new.chunk_id, new.content);
END;

DROP TRIGGER IF EXISTS knowledge_chunks_ad;
CREATE TRIGGER knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
    DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.chunk_id;
END;

-- Backfill any existing rows that may have been inserted before this migration
-- shipped (defensive: the application already writes to both tables).
INSERT OR IGNORE INTO knowledge_chunks_fts(chunk_id, content)
SELECT chunk_id, content FROM knowledge_chunks;
