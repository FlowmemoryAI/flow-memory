# Neural Memory Retrieval

Flow Memory v1 neural memory includes:

- `TinyMemoryEmbedder`: deterministic hashed bag-of-words vectors.
- `NeuralMemoryRetriever`: local in-memory cosine search.
- `TinyConsolidationModel`: relevance, recency, surprise, economic value, and safety importance scoring.

No external vector database is required. Redis/Qdrant/Neo4j remain optional adapter seams elsewhere in the project.
