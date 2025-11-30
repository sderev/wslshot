from __future__ import annotations

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
    if suffix in ('.jpg', '.jpeg'):
        format = "JPEG"
    elif suffix == '.gif':
        format = "GIF"
    else:
        format = "PNG"

    # Create a small valid image
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(path, format)
    return path
