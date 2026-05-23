from flow_memory.neural.memory.retriever import NeuralMemoryRetriever


def test_neural_memory_retriever_finds_similar_trace():
    retriever = NeuralMemoryRetriever()
    retriever.add("safety incident blocked unsafe wallet action")
    retriever.add("poem about flowers")
    hit = retriever.search("unsafe wallet safety", top_k=1)[0]
    assert "wallet" in hit.item
