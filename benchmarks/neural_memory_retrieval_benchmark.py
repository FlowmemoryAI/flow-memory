from __future__ import annotations

import json
from pathlib import Path

from flow_memory.neural.memory.retriever import NeuralMemoryRetriever


def main() -> dict[str, object]:
    retriever = NeuralMemoryRetriever()
    items = ("safety incident blocked unsafe tool", "economic settlement succeeded", "unrelated garden note")
    retriever.extend(items)
    hits = [hit.as_record() for hit in retriever.search("unsafe safety tool", top_k=2)]
    return {"ok": True, "top_k": hits}


if __name__ == "__main__":
    result = main()
    Path(".flow_memory").mkdir(exist_ok=True)
    Path(".flow_memory/neural_memory_retrieval_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
