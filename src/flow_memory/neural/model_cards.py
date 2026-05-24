"""Model card generation for imported GPU evidence."""
from __future__ import annotations
from flow_memory.neural.run_records import GpuRunSummary

def gpu_model_card(summary: GpuRunSummary) -> str:
    status = "skipped" if summary.skipped else "imported"
    return f"""# Flow Memory GPU validation evidence: {summary.run_id}

Status: {status}

- GPU: {summary.gpu_name or 'unknown'}
- Torch: {summary.torch_version or 'unknown'}
- CUDA available: {summary.cuda_available}
- CUDA version: {summary.cuda_version or 'unknown'}
- Git commit: {summary.git_commit or 'unknown'}
- CLI neural backend/status: {summary.cli_neural_backend or 'unknown'} / {summary.cli_neural_status or 'unknown'}

This is validation evidence for a tiny Flow Memory neural prototype. It is not production ML quality evidence and does not claim V-JEPA 2 or VideoMAE performance.
"""
