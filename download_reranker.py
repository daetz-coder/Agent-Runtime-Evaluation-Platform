"""Download bge-reranker-base model via ModelScope (China mirror) — ONNX only."""
from pathlib import Path

TARGET = Path(r"D:\Agent Runtime Evaluation Platform\example\wiki-agent\models\bge-reranker-base")
TARGET.parent.mkdir(parents=True, exist_ok=True)

# Check if the ONNX model file exists
onnx_file = TARGET / "onnx" / "model.onnx"
config_file = TARGET / "config.json"

if onnx_file.exists() and config_file.exists():
    print(f"[OK] ONNX model already exists at {TARGET}")
else:
    print(f"[Download] BAAI/bge-reranker-base (ONNX only) -> {TARGET}")
    from modelscope import snapshot_download
    result = snapshot_download(
        model_id="BAAI/bge-reranker-base",
        cache_dir=str(TARGET.parent / "_ms_cache"),
        local_dir=str(TARGET),
        ignore_patterns=[
            "pytorch_model.bin",
            "model.safetensors",
            "*.msgpack",
            "*.h5",
        ],
    )
    print(f"[OK] Done! Model saved to {result}")

# Remove redundant large files if they exist from a previous partial download
for redundant in ["pytorch_model.bin", "model.safetensors"]:
    p = TARGET / redundant
    if p.exists():
        size_mb = p.stat().st_size / 1024 / 1024
        p.unlink()
        print(f"[Cleaned] Removed {redundant} ({size_mb:.0f} MB)")

print("\n[Files]")
for f in sorted(TARGET.rglob("*")):
    if f.is_file():
        size_mb = f.stat().st_size / 1024 / 1024
        rel = f.relative_to(TARGET)
        print(f"  {str(rel):<50s} {size_mb:.1f} MB")
