import hashlib
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from app.core.config import DATA_DIR
from app.services.repository_service import ingest_repository

_GITHUB_REPO = re.compile(r"^/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$")
ProgressCallback = Callable[[str, str, int], None]


def normalize_github_url(raw_url: str) -> tuple[str, str]:
    """Accept only public HTTPS GitHub repository URLs."""
    url = raw_url.strip()
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"github.com", "www.github.com"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Enter a public GitHub URL such as https://github.com/owner/repository.")
    path = parsed.path[:-4] if parsed.path.endswith(".git") else parsed.path
    match = _GITHUB_REPO.fullmatch(path)
    if not match:
        raise ValueError("Use a repository URL, not a GitHub profile, file, or subdirectory URL.")
    owner, repo = match.groups()
    if repo in {".", ".."}:
        raise ValueError("Invalid repository name.")
    return f"https://github.com/{owner}/{repo}.git", repo


def _remove_checkout(path: Path) -> None:
    """Remove an app-managed checkout, retrying transient Windows file locks."""
    if not path.exists():
        return

    def handle_readonly(func, failed_path, _exc_info):
        try:
            os.chmod(failed_path, stat.S_IWRITE | stat.S_IREAD)
            func(failed_path)
        except OSError:
            raise

    last_error = None
    for attempt in range(5):
        try:
            shutil.rmtree(path, onerror=handle_readonly)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise ValueError(
        "The previous checkout is still locked by Windows or another process. "
        "Wait for the earlier indexing job to finish, then retry. "
        f"Checkout: {path}. Details: {last_error}"
    ) from last_error


def clone_and_index_public_repository(
    github_url: str,
    user_id: str,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    normalized_url, repo_name = normalize_github_url(github_url)
    repo_id = hashlib.sha256(f"{user_id}:{normalized_url.lower()}".encode()).hexdigest()[:24]
    user_key = hashlib.sha256(user_id.encode()).hexdigest()[:20]
    repos_root = (DATA_DIR / "repos").resolve()
    target = (repos_root / user_key / repo_id).resolve()
    if not target.is_relative_to(repos_root):
        raise ValueError("Invalid repository destination.")
    target.parent.mkdir(parents=True, exist_ok=True)

    def report(stage: str, message: str, progress: int):
        if progress_callback:
            progress_callback(stage, message, progress)

    # Duplicate active jobs are prevented in indexing_jobs.py. At this point no
    # other in-process job for this user/repository should be using this path.
    if target.exists():
        _remove_checkout(target)

    report("cloning", "Cloning public GitHub repository…", 8)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", normalized_url, str(target)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Git clone failed.").strip()
            raise ValueError(f"GitHub clone failed: {message[-500:]}")

        report("parsing", "Repository cloned. Discovering and parsing source files…", 35)
        ingest_result = ingest_repository(
            str(target),
            preserve_index_on_empty=True,
            progress_callback=progress_callback,
        )
        if ingest_result.get("chunks_indexed", 0) == 0:
            raise ValueError(
                "No supported Python, JavaScript, JSX, TypeScript, or TSX code chunks were indexed."
            )
        report("complete", "Repository connected and indexed successfully.", 100)
        return {
            "id": repo_id,
            "github_url": normalized_url.removesuffix(".git"),
            "name": repo_name,
            "local_path": str(target),
            **ingest_result,
        }
    except subprocess.TimeoutExpired as exc:
        if target.exists():
            try:
                _remove_checkout(target)
            except OSError:
                pass
        raise ValueError("Cloning took longer than 3 minutes. Try a smaller public repository.") from exc
    except Exception:
        if target.exists():
            try:
                _remove_checkout(target)
            except OSError:
                # Keep the original indexing error; the next retry will report
                # a precise locked-checkout message if cleanup is still needed.
                pass
        raise
