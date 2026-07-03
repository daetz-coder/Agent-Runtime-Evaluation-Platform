"""下载 Embedding 和 Reranker 模型权重。

用法:
    # 下载所有模型
    python -m app.wiki_agent.tools.download_models

    # 只下载 embedding
    python -m app.wiki_agent.tools.download_models --model embedding

    # 只下载 reranker
    python -m app.wiki_agent.tools.download_models --model reranker
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

WIKI_AGENT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = WIKI_AGENT_ROOT / "models"

EMBEDDING_MODEL_ID = "BAAI/bge-small-zh-v1.5"
RERANKER_MODEL_ID = "BAAI/bge-reranker-base"

WEIGHT_FILES = ("pytorch_model.bin", "model.safetensors")
TEMP_DIR_NAMES = ("._____temp", ".____temp")
MIN_WEIGHT_BYTES = 100_000_000  # 100MB minimum for valid weights


def _weight_is_valid(path: Path, name: str) -> bool:
    file_path = path / name
    if not file_path.exists():
        return False
    return file_path.stat().st_size >= MIN_WEIGHT_BYTES


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


def download_model(model_id: str, target: Path) -> None:
    """Download model from ModelScope."""
    print(f"[Download] {model_id} -> {target}")
    from modelscope import snapshot_download

    snapshot_download(
        model_id=model_id,
        cache_dir=str(target.parent / "_ms_cache"),
        local_dir=str(target),
    )
    print(f"[OK] {model_id} download finished")


def ensure_model(model_id: str, target: Path) -> bool:
    """Ensure model weights exist, download if needed. Returns True if ready."""
    target.mkdir(parents=True, exist_ok=True)

    removed = _remove_invalid_weights(target)
    if removed:
        print(f"[Cleaned] Removed incomplete weights: {', '.join(removed)}")

    promoted = promote_temp_weights(target)
    if promoted:
        print(f"[OK] Promoted weights: {', '.join(promoted)}")

    if _has_weights(target):
        print(f"[OK] {model_id} ready at {target}")
        return True

    download_model(model_id, target)

    if not _has_weights(target):
        print(f"[ERROR] No valid weights under {target}")
        return False

    return True


def print_model_files(target: Path) -> None:
    """Print model directory contents."""
    print(f"\n[Files] {target}")
    for f in sorted(target.rglob("*")):
        if f.is_file():
            size_mb = f.stat().st_size / 1024 / 1024
            rel = f.relative_to(target)
            print(f"  {str(rel):<50s} {size_mb:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Wiki Agent ML models")
    parser.add_argument(
        "--model",
        choices=["embedding", "reranker", "all"],
        default="all",
        help="Which model to download (default: all)",
    )
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    if args.model in ("embedding", "all"):
        target = MODELS_DIR / "bge-small-zh-v1.5"
        results["embedding"] = ensure_model(EMBEDDING_MODEL_ID, target)
        print_model_files(target)

    if args.model in ("reranker", "all"):
        target = MODELS_DIR / "bge-reranker-base"
        results["reranker"] = ensure_model(RERANKER_MODEL_ID, target)
        print_model_files(target)

    print("\n[Summary]")
    for name, ok in results.items():
        status = "✓ Ready" if ok else "✗ Failed"
        print(f"  {name}: {status}")

    if not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
