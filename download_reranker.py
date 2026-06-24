"""Download bge-reranker-base model via ModelScope (China mirror)."""
from pathlib import Path

TARGET = Path(r"D:\Agent Runtime Evaluation Platform\example\wiki-agent\models\bge-reranker-base")
TARGET.parent.mkdir(parents=True, exist_ok=True)

# Check if the actual model file exists (not just cache dirs)
model_file = TARGET / "pytorch_model.bin"
config_file = TARGET / "config.json"

if model_file.exists() and config_file.exists():
    print(f"[OK] Model already exists at {TARGET}")
else:
    print(f"[Download] BAAI/bge-reranker-base -> {TARGET}")
    from modelscope import snapshot_download
    result = snapshot_download(
        model_id="BAAI/bge-reranker-base",
        cache_dir=str(TARGET.parent / "_ms_cache"),
        local_dir=str(TARGET),
    )
    print(f"[OK] Done! Model saved to {result}")

print("\n[Files]")
for f in sorted(TARGET.rglob("*")):
    if f.is_file():
        size_mb = f.stat().st_size / 1024 / 1024
        rel = f.relative_to(TARGET)
        print(f"  {str(rel):<50s} {size_mb:.1f} MB")
