from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess

import pytest
from wslshot import cli

# ============================================================================
# Repository Detection Tests
# ============================================================================


def test_is_git_repo_returns_true_when_inside_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_git_repo() returns True when inside a git repository."""

    def fake_run(cmd, stdout, stderr, check):
        """Mock subprocess.run to simulate successful git command."""
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return CompletedProcess(cmd, 0)
        raise CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cli.is_git_repo() is True


def test_is_git_repo_returns_false_when_outside_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_git_repo() returns False when outside a git repository."""

    def fake_run(cmd, stdout, stderr, check):
        """Mock subprocess.run to simulate git command failure."""
        raise CalledProcessError(128, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cli.is_git_repo() is False


def test_is_git_repo_handles_subprocess_errors_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_git_repo() handles unexpected subprocess errors gracefully."""

    def fake_run(cmd, stdout, stderr, check):
        """Mock subprocess.run to raise CalledProcessError."""
        raise CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    # Should return False rather than crashing
    assert cli.is_git_repo() is False


# ============================================================================
# Getting Repository Root Tests
# ============================================================================


def test_get_git_root_returns_correct_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_git_root() returns the correct absolute path."""
    fake_root = "/home/user/projects/myrepo"

    def fake_run(cmd, check, stdout, stderr):
        """Mock subprocess.run to return git root path."""
        if cmd == ["git", "rev-parse", "--show-toplevel"]:
            result = CompletedProcess(cmd, 0)
            result.stdout = f"{fake_root}\n".encode("utf-8")
            return result
        raise CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = cli.get_git_root()

    assert isinstance(result, Path)
    assert result == Path(fake_root).resolve()


def test_get_git_root_handles_trailing_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_git_root() handles git command output with trailing newline."""
    fake_root = "/tmp/testrepo"

    def fake_run(cmd, check, stdout, stderr):
        """Mock subprocess.run with trailing newline in output."""
        if cmd == ["git", "rev-parse", "--show-toplevel"]:
            result = CompletedProcess(cmd, 0)
            # Simulate git output with newline
            result.stdout = f"{fake_root}\n".encode("utf-8")
            return result
        raise CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = cli.get_git_root()

    # Path should not include the newline
    assert str(result) == str(Path(fake_root).resolve())
    assert "\n" not in str(result)


def test_get_git_root_raises_runtime_error_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_git_root() raises RuntimeError when git command fails."""

    def fake_run(cmd, check, stdout, stderr):
        """Mock subprocess.run to raise CalledProcessError."""
        raise CalledProcessError(128, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        cli.get_git_root()


def test_get_git_root_error_message_is_informative(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_git_root() raises RuntimeError with informative error message."""

    def fake_run(cmd, check, stdout, stderr):
        """Mock subprocess.run to raise CalledProcessError."""
        raise CalledProcessError(128, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Failed to get git root directory"):
        cli.get_git_root()


# ============================================================================
# Image Destination Auto-Detection Tests
# ============================================================================


def test_get_git_repo_img_destination_prefers_img(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() prefers git_root/img/ if it exists."""
    git_root = tmp_path / "repo"
    git_root.mkdir()
    img_dir = git_root / "img"
    img_dir.mkdir()

    # Create other directories to ensure priority
    (git_root / "images").mkdir()
    (git_root / "assets").mkdir()
    (git_root / "assets" / "images").mkdir()

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    assert result == img_dir


def test_get_git_repo_img_destination_prefers_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() prefers git_root/images/ if img/ does not exist."""
    git_root = tmp_path / "repo"
    git_root.mkdir()
    images_dir = git_root / "images"
    images_dir.mkdir()

    # Create lower-priority directories
    (git_root / "assets").mkdir()
    (git_root / "assets" / "images").mkdir()

    # Do NOT create git_root/img

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    assert result == images_dir


def test_get_git_repo_img_destination_prefers_assets_img(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() prefers git_root/assets/img/ when higher priorities don't exist."""
    git_root = tmp_path / "repo"
    git_root.mkdir()
    assets_img_dir = git_root / "assets" / "img"
    assets_img_dir.mkdir(parents=True)

    # Create lower-priority directory
    (git_root / "assets" / "images").mkdir()

    # Do NOT create git_root/img or git_root/images

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    assert result == assets_img_dir


def test_get_git_repo_img_destination_prefers_assets_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() prefers git_root/assets/images/ if other options don't exist."""
    git_root = tmp_path / "repo"
    git_root.mkdir()
    assets_images_dir = git_root / "assets" / "images"
    assets_images_dir.mkdir(parents=True)

    # Do NOT create git_root/img, git_root/images, or git_root/assets/img

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    assert result == assets_images_dir


def test_get_git_repo_img_destination_creates_assets_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() creates git_root/assets/images/ when none exist."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    expected_dir = git_root / "assets" / "images"
    assert result == expected_dir
    assert expected_dir.exists()
    assert expected_dir.is_dir()


def test_get_git_repo_img_destination_priority_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() follows priority: img > images > assets/img > assets/images."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    # Test 1: No directories exist -> create assets/images
    result = cli.get_git_repo_img_destination()
    assert result == git_root / "assets" / "images"

    # Test 2: Only assets/images exists -> use it
    git_root2 = tmp_path / "repo2"
    git_root2.mkdir()
    (git_root2 / "assets" / "images").mkdir(parents=True)
    monkeypatch.setattr(cli, "get_git_root", lambda: git_root2)
    result = cli.get_git_repo_img_destination()
    assert result == git_root2 / "assets" / "images"

    # Test 3: assets/img exists -> use it (higher priority)
    git_root3 = tmp_path / "repo3"
    git_root3.mkdir()
    (git_root3 / "assets" / "images").mkdir(parents=True)
    (git_root3 / "assets" / "img").mkdir(parents=True)
    monkeypatch.setattr(cli, "get_git_root", lambda: git_root3)
    result = cli.get_git_repo_img_destination()
    assert result == git_root3 / "assets" / "img"

    # Test 4: images exists -> use it (higher priority)
    git_root4 = tmp_path / "repo4"
    git_root4.mkdir()
    (git_root4 / "assets" / "images").mkdir(parents=True)
    (git_root4 / "assets" / "img").mkdir(parents=True)
    (git_root4 / "images").mkdir()
    monkeypatch.setattr(cli, "get_git_root", lambda: git_root4)
    result = cli.get_git_repo_img_destination()
    assert result == git_root4 / "images"

    # Test 5: img exists -> use it (highest priority)
    git_root5 = tmp_path / "repo5"
    git_root5.mkdir()
    (git_root5 / "assets" / "images").mkdir(parents=True)
    (git_root5 / "assets" / "img").mkdir(parents=True)
    (git_root5 / "images").mkdir()
    (git_root5 / "img").mkdir()
    monkeypatch.setattr(cli, "get_git_root", lambda: git_root5)
    result = cli.get_git_repo_img_destination()
    assert result == git_root5 / "img"


def test_get_git_repo_img_destination_created_directory_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test get_git_repo_img_destination() creates directory with correct permissions."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    monkeypatch.setattr(cli, "get_git_root", lambda: git_root)

    result = cli.get_git_repo_img_destination()

    # Directory should exist and be writable
    assert result.exists()
    assert result.is_dir()
    # Verify we can write to it
    test_file = result / "test.txt"
    test_file.write_text("test")
    assert test_file.exists()


# ============================================================================
# Path Formatting for Git Tests
# ============================================================================


def test_format_screenshots_path_for_git_makes_paths_relative(tmp_path: Path) -> None:
    """Test format_screenshots_path_for_git() makes absolute paths relative to git root."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    screenshots = (
        git_root / "assets" / "images" / "screenshot1.png",
        git_root / "img" / "screenshot2.png",
    )

    result = cli.format_screenshots_path_for_git(screenshots, git_root)

    assert result == (
        Path("assets/images/screenshot1.png"),
        Path("img/screenshot2.png"),
    )


def test_format_screenshots_path_for_git_skips_outside_paths(tmp_path: Path) -> None:
    """Test format_screenshots_path_for_git() skips paths outside git root."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    inside = git_root / "assets" / "images" / "inside.png"
    outside = tmp_path / "other" / "outside.png"

    result = cli.format_screenshots_path_for_git((inside, outside), git_root)

    # Only the inside path should be included
    assert result == (Path("assets/images/inside.png"),)


def test_format_screenshots_path_for_git_handles_empty_input(tmp_path: Path) -> None:
    """Test format_screenshots_path_for_git() handles empty input tuple."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    result = cli.format_screenshots_path_for_git((), git_root)

    assert result == ()


def test_format_screenshots_path_for_git_mixed_inside_outside(tmp_path: Path) -> None:
    """Test format_screenshots_path_for_git() with multiple paths, some inside and some outside repo."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    screenshots = (
        git_root / "img" / "shot1.png",
        tmp_path / "external" / "shot2.png",
        git_root / "assets" / "images" / "shot3.png",
        tmp_path / "another" / "shot4.png",
        git_root / "shot5.png",
    )

    result = cli.format_screenshots_path_for_git(screenshots, git_root)

    # Only paths inside git_root should be included
    assert result == (
        Path("img/shot1.png"),
        Path("assets/images/shot3.png"),
        Path("shot5.png"),
    )


# ============================================================================
# Staging Screenshots Tests
# ============================================================================


def test_stage_screenshots_calls_git_add(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test stage_screenshots() calls git add with correct arguments (batched)."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    called_commands = []

    def fake_run(cmd, check, cwd):
        """Mock subprocess.run to capture git commands."""
        called_commands.append(cmd)
        return CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    screenshots = (
        Path("assets/images/shot1.png"),
        Path("img/shot2.png"),
    )

    cli.stage_screenshots(screenshots, git_root)

    # Should batch all files into a single git add command
    assert called_commands == [
        ["git", "add", "assets/images/shot1.png", "img/shot2.png"],
    ]


def test_stage_screenshots_runs_from_git_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test stage_screenshots() runs git add from correct working directory (git_root)."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    called_cwd = []

    def fake_run(cmd, check, cwd):
        """Mock subprocess.run to capture working directory."""
        called_cwd.append(cwd)
        return CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    screenshots = (Path("assets/images/shot.png"),)

    cli.stage_screenshots(screenshots, git_root)

    # Verify git add was called from git_root
    assert called_cwd == [git_root]


def test_stage_screenshots_handles_called_process_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """Test stage_screenshots() handles CalledProcessError gracefully (prints error but doesn't crash)."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    def fake_run(cmd, check, cwd):
        """Mock subprocess.run to raise CalledProcessError."""
        raise CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    screenshots = (Path("assets/images/shot.png"),)

    # Should not raise an exception
    cli.stage_screenshots(screenshots, git_root)

    # Should print error message to stderr
    captured = capsys.readouterr()
    assert "Failed to stage screenshots" in captured.err


def test_stage_screenshots_stages_multiple_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test stage_screenshots() stages multiple files correctly with batched git add."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    called_commands = []

    def fake_run(cmd, check, cwd):
        """Mock subprocess.run to capture all git add commands."""
        called_commands.append(cmd)
        return CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    screenshots = (
        Path("img/shot1.png"),
        Path("img/shot2.png"),
        Path("assets/images/shot3.png"),
    )

    cli.stage_screenshots(screenshots, git_root)

    # All files should be staged with a single batched git add command
    assert len(called_commands) == 1
    assert called_commands[0] == [
        "git",
        "add",
        "img/shot1.png",
        "img/shot2.png",
        "assets/images/shot3.png",
    ]
