# GPU cost controls

Use the cheapest GPU that proves the lane first. For Flow Memory Neural v1, an RTX 4090 or RTX 5090 is enough for smoke validation. Use A100 80 GB only when larger checkpoints or batches require it.

Cost controls:
- Start with a one-hour smoke test.
- Move to a four-hour training run only after smoke validation passes.
- Use overnight runs only with artifact backup and a clear stop/delete plan.
- Stop or delete pods when done. Verify in the provider console whether volumes/storage keep billing.
- Back up `artifacts/cloud_gpu/*.tar.gz` before deleting.
- Do not download checkpoints automatically.
- Do not commit model weights.

Example budget buckets to verify in the provider console:
- One-hour smoke: validate install, CUDA, examples, benchmarks.
- Four-hour run: tiny training experiments and repeated benchmarks.
- Overnight run: larger synthetic sweeps only after scripts are stable.

Prices change by provider and GPU; always verify in the console before launch.
