from pathlib import Path

# File types we want to understand in the first version.
SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "coverage",
    ".idea",
    ".vscode",
}

MAX_FILE_BYTES = 500_000

# def discover_source_files(repository_path: str) -> list[Path]:
#     """
#     Find supported source files inside a repository.

#     Returns paths relative to the repository root.
#     """

#     root = Path(repository_path).expanduser().resolve()

#     if not root.exists():
#         raise ValueError(f"Repository path does not exist: {root}")

#     if not root.is_dir():
#         raise ValueError("Repository path must be a directory")

#     files = []

#     for path in root.rglob("*"):
#         if not path.is_file():
#             continue

#         relative_path = path.relative_to(root)

#         # Skip files inside ignored directories.
#         if any(
#             part in IGNORED_DIRECTORIES
#             for part in relative_path.parts
#         ):
#             continue

#         if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
#             continue

#         try:
#             if path.stat().st_size > MAX_FILE_BYTES: # retrieve the size of a file
#                 continue
#         except OSError:
#             continue

#         files.append(relative_path)

#     return sorted(files,key=lambda item: item.as_posix()) # item.as_posix() converts each Path object to a POSIX-style string path (forward slashes /), which is then used for sorting.


def discover_source_files(repository_path: str) -> list[Path]:
    """
    Find supported source files inside a repository.

    Prunes ignored directories before traversing them.
    Returns paths relative to the repository root.
    """
    import os

    root = Path(repository_path).expanduser().resolve()

    if not root.exists():
        raise ValueError(f"Repository path does not exist: {root}")

    if not root.is_dir():
        raise ValueError("Repository path must be a directory")

    files = []

    for current_root, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        # Prevent traversal into ignored directories.
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in IGNORED_DIRECTORIES
        )

        current_path = Path(current_root)

        for file_name in file_names:
            path = current_path / file_name

            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            files.append(path.relative_to(root))

    return sorted(files, key=lambda item: item.as_posix())


def read_source_file(
    repository_path: str,
    relative_path: Path,
) -> str:
    """
    Read a discovered file without allowing paths outside the repository.
    """
    root = Path(repository_path).expanduser().resolve()
    target = (root / relative_path).resolve()

    if not target.is_relative_to(root):
        raise ValueError("File path escapes the repository.")

    if not target.is_file():
        raise ValueError("Source file does not exist.")

    if target.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported source file type.")

    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Source file exceeds the size limit.")

    return target.read_text(
        encoding="utf-8",
        errors="replace",
    )
