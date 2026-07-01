"""基于 GitPython 的知识库版本管理"""

from __future__ import annotations

import difflib
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from app.wiki_agent.config import settings
from app.wiki_agent.wiki.schemas import WikiCommit, WikiDiff, WikiDiffHunk, WikiDiffLine

KNOWLEDGE_DIR = Path(settings.KNOWLEDGE_DIR)


def _get_repo() -> Repo | None:
    """获取 git repo，如果不存在则初始化"""
    if not settings.GIT_ENABLED:
        return None
    try:
        return Repo(KNOWLEDGE_DIR)
    except InvalidGitRepositoryError:
        return Repo.init(KNOWLEDGE_DIR)


def commit_changes(message: str, files: list[str] | None = None) -> str | None:
    """提交变更，返回 commit hash"""
    repo = _get_repo()
    if repo is None:
        return None

    if files:
        for f in files:
            repo.index.add([f])
    else:
        repo.index.add("*")

    # 检查是否有变更
    has_changes = False
    try:
        has_changes = bool(repo.index.diff("HEAD")) or bool(repo.untracked_files)
    except Exception:
        # 首次提交：HEAD 不存在，检查暂存区
        has_changes = len(repo.index.entries) > 0

    if not has_changes:
        return None

    commit = repo.index.commit(message)
    return commit.hexsha[:8]


def _files_in_commit(commit) -> list[str]:
    """从 diff 提取该提交涉及的路径（比 stats.files 更完整）"""
    paths: set[str] = set()

    try:
        if commit.parents:
            parent = commit.parents[0]
            for diff_item in parent.diff(commit):
                path = diff_item.b_path or diff_item.a_path
                if path:
                    paths.add(path.replace("\\", "/"))
        else:
            for item in commit.tree.traverse():
                if item.type == "blob":
                    paths.add(item.path.replace("\\", "/"))
    except Exception:
        pass

    if not paths:
        try:
            paths.update(k.replace("\\", "/") for k in commit.stats.files.keys())
        except Exception:
            pass

    return sorted(paths)


def get_history(rel_path: str | None = None, limit: int = 20) -> list[WikiCommit]:
    """获取变更历史"""
    repo = _get_repo()
    if repo is None:
        return []

    commits = []
    try:
        for commit in repo.iter_commits(paths=rel_path, max_count=limit):
            parent = commit.parents[0].hexsha[:8] if commit.parents else None
            commits.append(
                WikiCommit(
                    hash=commit.hexsha[:8],
                    message=commit.message.strip(),
                    date=commit.committed_datetime.isoformat(timespec="seconds"),
                    files=_files_in_commit(commit),
                    parent_hash=parent,
                )
            )
    except Exception:
        pass
    return commits


def get_diff(rel_path: str, hash_a: str, hash_b: str = "HEAD") -> str:
    """获取两个版本之间的 diff"""
    repo = _get_repo()
    if repo is None:
        return ""

    try:
        a = repo.commit(hash_a)
        b = repo.commit(hash_b)
        diff = a.diff(b, paths=rel_path)
        if diff:
            return diff[0].diff.decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def get_file_at_commit(rel_path: str, commit_hash: str) -> str:
    """获取指定版本的文件内容"""
    repo = _get_repo()
    if repo is None:
        return ""

    try:
        commit = repo.commit(commit_hash)
        blob = commit.tree / rel_path
        return blob.data_stream.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def get_structured_diff(rel_path: str, hash_a: str, hash_b: str = "HEAD") -> WikiDiff:
    """获取两个版本之间的结构化 diff"""
    old_content = get_file_at_commit(rel_path, hash_a)
    new_content = get_file_at_commit(rel_path, hash_b)

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    differ = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"{rel_path}@{hash_a}",
        tofile=f"{rel_path}@{hash_b}",
        lineterm="",
    )

    hunks: list[WikiDiffHunk] = []
    current_hunk: WikiDiffHunk | None = None
    old_line = 0
    new_line = 0

    for line in differ:
        # 解析 hunk header: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith("@@"):
            if current_hunk and current_hunk.lines:
                hunks.append(current_hunk)
            current_hunk = WikiDiffHunk(header=line)
            import re
            m = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                old_line = int(m.group(1))
                new_line = int(m.group(2))
            continue

        if current_hunk is None:
            current_hunk = WikiDiffHunk(header="")

        if line.startswith("+"):
            current_hunk.lines.append(WikiDiffLine(
                type="add", content=line[1:], old_line=None, new_line=new_line
            ))
            new_line += 1
        elif line.startswith("-"):
            current_hunk.lines.append(WikiDiffLine(
                type="remove", content=line[1:], old_line=old_line, new_line=None
            ))
            old_line += 1
        else:
            # context line (starts with space or is empty)
            content = line[1:] if line.startswith(" ") else line
            current_hunk.lines.append(WikiDiffLine(
                type="context", content=content, old_line=old_line, new_line=new_line
            ))
            old_line += 1
            new_line += 1

    if current_hunk and current_hunk.lines:
        hunks.append(current_hunk)

    return WikiDiff(
        path=rel_path,
        old_hash=hash_a,
        new_hash=hash_b,
        old_content=old_content,
        new_content=new_content,
        hunks=hunks,
    )


def rollback(rel_path: str, commit_hash: str) -> bool:
    """回滚指定文件到指定版本"""
    repo = _get_repo()
    if repo is None:
        return False

    try:
        commit = repo.commit(commit_hash)
        blob = commit.tree / rel_path
        file_path = KNOWLEDGE_DIR / rel_path
        file_path.write_bytes(blob.data_stream.read())
        repo.index.add([rel_path])
        repo.index.commit(f"回滚 {rel_path} 到 {commit_hash[:8]}")
        return True
    except Exception:
        return False
