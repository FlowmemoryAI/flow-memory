# Neural Backends

## Implemented
- `none`: default, no neural dependencies.
- `tiny_torch`: optional CPU-safe PyTorch prototype.

## Adapter seams
- `vjepa2`: requires explicit local checkpoint and local runtime code. No downloads.
- `videomae`: requires explicit local checkpoint and local runtime code. No downloads.

Install optional ML dependencies:

```bash
pip install -e ".[ml]"
```

No checkpoints are downloaded automatically.
