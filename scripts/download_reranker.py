"""Download bge-reranker-base PyTorch weights for CrossEncoder reranking."""
from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TARGET = PROJECT_ROOT / "example" / "wiki-agent" / "models" / "bge-reranker-base"
TARGET.parent.mkdir(parents=True, exist_ok=True)

WEIGHT_FILES = ("pytorch_model.bin", "model.safetensors")
TEMP_DIR_NAMES = ("._____temp", ".____temp")
# bge-reranker-base PyTorch bin is ~1.1GB; smaller files are partial downloads.
MIN_PYTORCH_BYTES = 900_000_000
MIN_SAFETENSORS_BYTES = 900_000_000


def _weight_is_valid(path: Path, name: str) -> bool:
    file_path = path / name
    if not file_path.exists():
        return False
    size = file_path.stat().st_size
    if name == "pytorch_model.bin":
        return size >= MIN_PYTORCH_BYTES
    if name == "model.safetensors":
        return size >= MIN_SAFETENSORS_BYTES
    return False


def _has_weights(path: Path) -> bool:
    return any(_weight_is_valid(path, name) for name in WEIGHT_FILES)


def _remove_invalid_weights(target: Path) -> list[str]:
    removed: list[str] = []
    for name in WEIGHT_FILES:
        file_path = target / name
        if file_path.exists() and not _weight_is_valid(target, name):
            size_mb = file_path.stat().st_size / 1024 / 1024
            file_path.unlink()
            removed.append(f"{name} ({size_mb:.0f} MB, incomplete)")
    return removed


def promote_temp_weights(target: Path) -> list[str]:
    """Move partial ModelScope downloads from temp subdirs into model root."""
    promoted: list[str] = []
    for temp_name in TEMP_DIR_NAMES:
        temp_dir = target / temp_name
        if not temp_dir.is_dir():
            continue
        for name in WEIGHT_FILES:
            src = temp_dir / name
            dst = target / name
            if src.exists() and not dst.exists() and _weight_is_valid(temp_dir, name):
                shutil.move(str(src), str(dst))
                promoted.append(name)
                size_mb = dst.stat().st_size / 1024 / 1024
                print(f"[Promoted] {temp_name}/{name} -> {name} ({size_mb:.0f} MB)")
            elif src.exists() and not _weight_is_valid(temp_dir, name):
                size_mb = src.stat().st_size / 1024 / 1024
                print(f"[Skip] {temp_name}/{name} incomplete ({size_mb:.0f} MB)")
    return promoted


def download_pytorch_weights(target: Path) -> None:
    print(f"[Download] BAAI/bge-reranker-base (PyTorch) -> {target}")
    from modelscope import snapshot_download

    snapshot_download(
        model_id="BAAI/bge-reranker-base",
        cache_dir=str(target.parent / "_ms_cache"),
        local_dir=str(target),
    )
    print("[OK] Download finished")


def main() -> None:
    removed = _remove_invalid_weights(TARGET)
    if removed:
        print(f"[Cleaned] Removed incomplete weights: {', '.join(removed)}")

    promoted = promote_temp_weights(TARGET)
    if promoted:
        print(f"[OK] Promoted weights: {', '.join(promoted)}")

    if _has_weights(TARGET):
        print(f"[OK] Reranker PyTorch weights ready at {TARGET}")
    else:
        download_pytorch_weights(TARGET)

    if not _has_weights(TARGET):
        raise SystemExit(
            f"[ERROR] No PyTorch weights under {TARGET}. "
            "CrossEncoder requires pytorch_model.bin or model.safetensors at the model root."
        )

    print("\n[Files]")
    for f in sorted(TARGET.rglob("*")):
        if f.is_file():
            size_mb = f.stat().st_size / 1024 / 1024
            rel = f.relative_to(TARGET)
            print(f"  {str(rel):<50s} {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
