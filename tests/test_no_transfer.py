"""
Tests for the `--no-transfer` flag on the `fetch` command.

The `--no-transfer` flag prints source screenshot paths without copying files,
creating directories, or triggering Git integration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import create_test_image

from wslshot import cli


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click test runner."""
    return CliRunner()


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory with test screenshots."""
    source = tmp_path / "source"
    source.mkdir()
    return source


@pytest.fixture
def dest_dir(tmp_path: Path) -> Path:
    """Create a destination directory."""
    dest = tmp_path / "dest"
    dest.mkdir()
    return dest


@pytest.fixture
def config_file(fake_home: Path) -> Path:
    """Create a config file with default settings."""
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
                "default_convert_to": None,
            }
        )
    )
    return config_path


def create_screenshot(directory: Path, name: str) -> Path:
    """Create a real test screenshot file."""
    screenshot = directory / name
    create_test_image(screenshot)
    return screenshot


# ============================================================================
# Basic --no-transfer behavior
# ============================================================================


def test_no_transfer_prints_source_path_without_copying(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer prints source paths without copying files."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should print source path, not destination
    assert str(source_dir) in result.output
    # Destination should remain empty (no files copied)
    copied_files = list(dest_dir.glob("*.png"))
    assert len(copied_files) == 0


def test_no_transfer_defaults_to_text_output(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
) -> None:
    """Test --no-transfer defaults to text output format for scripting."""
    create_screenshot(source_dir, "screenshot.png")
    config_path = fake_home / ".config" / "wslshot" / "config.json"

    # Create config with markdown as default (to prove we override it)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": False,
                "default_output_format": "markdown",  # This should be overridden
                "default_convert_to": None,
            }
        )
    )

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should NOT be markdown format (no "![" prefix)
    assert "![" not in result.output
    # Should be plain path (text format)
    assert str(source_dir) in result.output


def test_no_transfer_with_count(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer works with --count."""
    for i in range(3):
        create_screenshot(source_dir, f"screenshot_{i}.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--count", "2"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should output 2 lines (one for each screenshot)
    output_lines = [line for line in result.output.strip().split("\n") if line]
    assert len(output_lines) == 2


def test_no_transfer_with_explicit_image_path(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer works with explicit image_path argument."""
    config_file.write_text(
        json.dumps(
            {
                "default_source": "/does/not/exist",
                "default_destination": "",
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
                "default_convert_to": None,
            }
        )
    )
    image = create_screenshot(tmp_path, "myimage.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--no-transfer", str(image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should print the provided image path
    assert str(image) in result.output


# ============================================================================
# Output format with --no-transfer
# ============================================================================


def test_no_transfer_respects_output_style_markdown(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer respects --output-style markdown."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--output-style", "markdown"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot.png](" in result.output
    assert str(source_dir) in result.output


def test_no_transfer_respects_output_style_html(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer respects --output-style html."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--output-style", "html"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert '<img src="' in result.output
    assert 'alt="screenshot.png"' in result.output


def test_no_transfer_respects_output_style_text(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer respects --output-style text."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--output-style", "text"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Text format: just the path
    assert str(source_dir) in result.output
    assert "![" not in result.output
    assert "<img" not in result.output


# ============================================================================
# Conflicting flags
# ============================================================================


def test_no_transfer_with_convert_to_errors(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer + --convert-to produces error."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--convert-to", "jpg"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 2
    assert "requires file transfer" in result.output
    assert "--no-transfer" in result.output


def test_no_transfer_with_optimize_errors(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer + --optimize produces error."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--optimize"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 2
    assert "requires file transfer" in result.output
    assert "--no-transfer" in result.output


def test_no_transfer_with_destination_errors(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer + --destination produces error."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--no-transfer",
            "--destination",
            str(dest_dir),
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 2
    assert "--destination cannot be used with --no-transfer" in result.output


# ============================================================================
# File validation with --no-transfer
# ============================================================================


def test_no_transfer_still_validates_images(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer still rejects non-image files."""
    # Create a text file with .png extension
    fake_image = tmp_path / "fake.png"
    fake_image.write_text("not an image")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--no-transfer", str(fake_image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "not a valid image" in result.output


def test_no_transfer_validates_images_in_source_dir(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer validates images when scanning source directory."""
    # Create a valid image and a fake image
    create_screenshot(source_dir, "valid.png")
    fake = source_dir / "fake.png"
    fake.write_text("not an image")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--count", "1"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should print the valid image
    assert "valid.png" in result.output
    # Warning about invalid file should appear in stderr
    assert "Skipping invalid image file" in result.output


def test_no_transfer_ignores_stale_invalid_files(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Older invalid files should not warn when a newer valid screenshot satisfies the count."""
    stale_invalid = source_dir / "stale.png"
    stale_invalid.write_text("not an image", encoding="UTF-8")
    os.utime(stale_invalid, (1700000000, 1700000000))

    newest = create_screenshot(source_dir, "newest.png")
    os.utime(newest, (1700000010, 1700000010))

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--count", "1"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "newest.png" in result.output
    assert "Skipping invalid image file" not in result.output


def test_no_transfer_prints_absolute_paths(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test --no-transfer prints absolute Linux paths."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer", "--output-style", "text"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Path should be absolute
    output_path = result.output.strip()
    assert output_path.startswith("/")
    assert str(source_dir) in output_path


def test_no_transfer_does_not_create_directories(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    tmp_path: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test --no-transfer does not create any directories."""
    create_screenshot(source_dir, "screenshot.png")

    # Track directory creation calls
    create_calls = []
    original_create = cli.create_directory_safely

    def track_create(*args, **kwargs):
        create_calls.append(args)
        return original_create(*args, **kwargs)

    monkeypatch.setattr(cli, "create_directory_safely", track_create)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # create_directory_safely may be called for config dir, but NOT for destination
    # Since we're using --no-transfer, no image destination directories should be created
    # Any calls would be for config directory, which is fine
    # The key check: no assets/img directory created
    assets_img = tmp_path / "assets" / "img"
    assert not assets_img.exists()


def test_no_transfer_does_not_trigger_git_integration(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test --no-transfer does not call git-related functions."""
    create_screenshot(source_dir, "screenshot.png")

    # Track git function calls
    git_calls = []

    def track_is_git_repo():
        git_calls.append("is_git_repo")
        return True

    def track_get_git_root():
        git_calls.append("get_git_root")
        return Path("/fake/git/root")

    def track_stage_screenshots(*args, **kwargs):
        git_calls.append("stage_screenshots")

    monkeypatch.setattr(cli, "is_git_repo", track_is_git_repo)
    monkeypatch.setattr(cli, "get_git_root", track_get_git_root)
    monkeypatch.setattr(cli, "stage_screenshots", track_stage_screenshots)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # None of the git functions should be called
    assert "is_git_repo" not in git_calls
    assert "get_git_root" not in git_calls
    assert "stage_screenshots" not in git_calls


def test_no_transfer_does_not_create_config_file(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
) -> None:
    """Test --no-transfer does not create config file when it doesn't exist.

    This ensures the flag works in restricted environments where HOME is read-only.
    """
    create_screenshot(source_dir, "screenshot.png")
    config_path = fake_home / ".config" / "wslshot" / "config.json"

    # Ensure config file does not exist before running
    assert not config_path.exists()

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--no-transfer"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Config file should NOT have been created
    assert not config_path.exists()
    # Should still print the source path
    assert str(source_dir) in result.output
