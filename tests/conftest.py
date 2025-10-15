from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
