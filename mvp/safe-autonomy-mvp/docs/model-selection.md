# Model and resource selection for v0.6-dev

## Advisory Transformer

`Qwen3-4B-Instruct-2507` is the default ground-station advisory model. The official model card describes a 4B non-thinking instruction model with tool-use improvements and native long context. This project deliberately caps runtime context to 8192 tokens because the target development computer has 12 GB RAM and retrieval should provide a small evidence set rather than fill the full model context.

Source: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507

The model is not scheduled on the Jetson real-time perception path. On an Orin Nano 8 GB, GPU priority belongs to YOLO, depth and tracking; advisory generation is load-shed first.

For the Jetson AGX 64GB development target, unified memory is explicitly divided among OS/CUDA reserve, vision, local LLM, retrieval models, map planning and database/stream buffers in `config/jetson_agx_64gb.json`. The realtime priority order is telemetry/vision/safety first, deterministic route planning second and RAG/LLM last. These are development budgets and must be replaced by measured P50/P95/P99 values on the exact JetPack/TensorRT build.

## Embedding and reranking

- `Qwen3-Embedding-0.6B`: multilingual embedding, 32K context, up to 1024 dimensions.
- `Qwen3-Reranker-0.6B`: multilingual cross-encoder reranker, 32K context.

Official model cards report support for more than 100 languages and provide Sentence Transformers integration. The 0.6B variants are chosen instead of 4B/8B because the development machine cannot reliably host the advisory model, embedder and reranker concurrently at their largest sizes.

Sources:

- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- https://huggingface.co/Qwen/Qwen3-Reranker-0.6B

## Retrieval architecture

Developer mode uses SQLite FTS5 plus a dense embedding column and a relational property graph. Production migration targets:

- Qdrant dense/sparse hybrid Query API with Reciprocal Rank Fusion: https://qdrant.tech/documentation/search/hybrid-queries/
- Neo4j GraphRAG and property graph storage: https://neo4j.com/docs/neo4j-graphrag-python/current/

The deterministic Hashing embedder and TokenOverlap reranker exist only so tests run offline. They are never represented as Transformer-quality models.
