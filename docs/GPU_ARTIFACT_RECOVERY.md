# GPU Artifact Recovery

The stronger neural GPU release gates require the real RunPod tarball:

```text
artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
```

If it is missing, the expected blocker is:

```text
gpu_evidence_verified_run_missing
```

Run:

```powershell
cd E:\FlowMemory\flow-memory
mkdir artifacts\incoming -Force
Copy-Item "$env:USERPROFILE\Downloads\flow-memory-cloud-gpu-run-001.tar.gz" `
  "artifacts\incoming\flow-memory-cloud-gpu-run-001.tar.gz" `
  -Force
python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001
python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001
python scripts/export_release_evidence.py
python scripts/verify_release_evidence.py
python scripts/release_decision.py --target neural-gpu-smoke
```

Do not commit raw model weights or large artifacts. Do not fake evidence. If the tarball is absent, keep the gate blocked and continue other launch work.
