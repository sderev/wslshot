from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator

import pytest
from PIL import Image


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Provide an isolated HOME directory so config writes stay in the tmp sandbox.
    """
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    config_dir = home_dir / ".config" / "wslshot"
    config_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", lambda: home_dir)

    yield home_dir


@pytest.fixture
def temp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Execute code under a temporary working directory.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def create_test_image(path: Path, format: str = "PNG") -> Path:
    """
    Create a valid test image file.

    Args:
        path: Path where the image should be created
        format: Image format (PNG, JPEG, GIF)

    Returns:
        Path to the created image
    """
    # Determine format from extension if not explicitly provided
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        format = "JPEG"
    elif suffix == ".gif":
        format = "GIF"
    else:
        format = "PNG"

    # Create a small valid image
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(path, format)
    return path


def create_git_repo(path: Path) -> Path:
    """Initialize git repo with minimal config (no network ops)."""
    subprocess.run(["git", "init"], cwd=path, check=True)
    empty_hooks = path / ".git" / "hooks-empty"
    empty_hooks.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(empty_hooks)],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=path,
        check=True,
    )
    return path


def get_staged_files(repo_path: Path) -> list[str]:
    """Return list of staged files (relative paths).

    Handles git's quoting behavior for filenames with special characters.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Git quotes filenames with special characters (unicode, spaces, etc.)
        # Format: "filename_\346\227\245\346\234\254\350\252\236.png"
        if line.startswith('"') and line.endswith('"'):
            # Remove quotes and decode escape sequences
            line = line[1:-1]
            # Decode octal escape sequences (\346 -> byte)
            line = line.encode("utf-8").decode("unicode_escape").encode("latin1").decode("utf-8")
        files.append(line)
    return files


def is_file_staged(repo_path: Path, file_path: Path) -> bool:
    """Check if specific file is staged."""
    staged = get_staged_files(repo_path)
    # Handle both absolute and relative paths
    try:
        relative = file_path.relative_to(repo_path) if file_path.is_absolute() else file_path
    except ValueError:
        return False
    return str(relative) in staged
