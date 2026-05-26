from flow_memory.neural.memory.embedder import TinyMemoryEmbedder


def test_tiny_memory_embedder_deterministic() -> None:
    embedder = TinyMemoryEmbedder(dimensions=16)
    assert embedder.embed("safety incident") == embedder.embed("safety incident")
