"""
Comprehensive integration tests for the wslshot fetch command.

These tests verify the main CLI command behavior including:
- Basic fetch operations with different options
- Image path argument handling
- Source/destination validation
- Output format validation
- Git integration scenarios
- Screenshot fetching logic
- Output formatting verification
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from wslshot import cli
from conftest import create_test_image

# ============================================================================
# Fixtures and Helpers
# ============================================================================


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
# 1. Basic Fetch Operations
# ============================================================================


def test_fetch_with_default_settings(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test fetch with default settings from config."""
    # Update config with default directories
    config_file.write_text(
        json.dumps(
            {
                "default_source": str(source_dir),
                "default_destination": str(dest_dir),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    create_screenshot(source_dir, "screenshot.png")

    # Mock is_git_repo to False so it uses config default_destination
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = runner.invoke(
        cli.wslshot,
        ["fetch"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output
    assert str(dest_dir) in result.output


def test_fetch_with_custom_source(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch command with custom --source."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output


def test_fetch_with_custom_destination(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch command with custom --destination."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert str(dest_dir) in result.output


def test_fetch_with_count_3(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --count 3."""
    # Create 3 screenshots with different timestamps
    for i in range(3):
        screenshot = create_screenshot(source_dir, f"screenshot_{i}.png")
        # Touch to ensure different modification times
        create_test_image(screenshot)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir), "--count", "3"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should output 3 lines (one for each screenshot)
    output_lines = [line for line in result.output.strip().split("\n") if line]
    assert len(output_lines) == 3


def test_fetch_with_output_format_markdown(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style markdown."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "markdown",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output
    assert "](" in result.output


def test_fetch_with_output_format_html(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style html."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "html",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert '<img src="' in result.output
    assert 'alt="screenshot_' in result.output


def test_fetch_with_output_format_plain_text(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style text."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "text",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Text format should just show the path
    assert str(dest_dir) in result.output
    # Should not contain markdown or html formatting
    assert "![" not in result.output
    assert "<img" not in result.output


def test_fetch_with_output_style_markdown(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style markdown (new option name)."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "markdown",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output
    assert "](" in result.output


def test_fetch_with_output_style_html(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style html (new option name)."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "html",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert '<img src="' in result.output
    assert 'alt="screenshot_' in result.output


def test_fetch_with_output_style_text(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --output-style text (new option name)."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "text",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Text should just show the path
    assert str(dest_dir) in result.output
    # Should not contain markdown or html formatting
    assert "![" not in result.output
    assert "<img" not in result.output


def test_fetch_output_style_no_deprecation_warning(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test that using --output-style does NOT show a deprecation warning."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "markdown",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    warning_output = result.stderr or result.output

    # Should NOT show warning about --output-format
    assert "--output-format" not in warning_output
    assert "deprecated" not in warning_output


def test_fetch_with_all_options_combined(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with all options combined."""
    create_screenshot(source_dir, "screenshot1.png")
    create_screenshot(source_dir, "screenshot2.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--count",
            "2",
            "--output-style",
            "html",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert '<img src="' in result.output


def test_fetch_default_count_is_1(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test default count is 1."""
    create_screenshot(source_dir, "screenshot1.png")
    create_screenshot(source_dir, "screenshot2.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should only output 1 line
    output_lines = [line for line in result.output.strip().split("\n") if line]
    assert len(output_lines) == 1


# ============================================================================
# 2. Image Path Argument
# ============================================================================


def test_fetch_with_direct_png_path(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with direct PNG path."""
    image = create_screenshot(tmp_path, "myimage.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output


def test_fetch_with_direct_jpg_path(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with direct JPG path."""
    image = create_screenshot(tmp_path, "myimage.jpg")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output


def test_fetch_with_direct_gif_path(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with direct GIF path."""
    image = create_screenshot(tmp_path, "myimage.gif")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # GIF files should use 'animated_' prefix
    assert "![animated_" in result.output


def test_fetch_with_direct_jpeg_path(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with direct JPEG path."""
    image = create_screenshot(tmp_path, "myimage.jpeg")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(image)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "![screenshot_" in result.output


def test_fetch_rejects_txt_file(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test rejects .txt file (invalid format)."""
    text_file = tmp_path / "file.txt"
    text_file.write_text("not an image")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(text_file)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    # New validation provides more accurate error message
    assert "not a valid image" in result.output


def test_fetch_rejects_pdf_file(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test rejects .pdf file (invalid format)."""
    pdf_file = tmp_path / "file.pdf"
    pdf_file.write_bytes(b"fake pdf data")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(pdf_file)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    # New validation provides more accurate error message
    assert "not a valid image" in result.output


def test_fetch_handles_uppercase_extensions(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test handles uppercase extensions (.PNG, .GIF)."""
    png_image = create_screenshot(tmp_path, "image.PNG")
    result_png = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(png_image)],
        env={"HOME": str(fake_home)},
    )
    assert result_png.exit_code == 0

    gif_image = create_screenshot(tmp_path, "image.GIF")
    result_gif = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(gif_image)],
        env={"HOME": str(fake_home)},
    )
    assert result_gif.exit_code == 0


def test_fetch_error_message_for_unsupported_format(
    runner: CliRunner,
    fake_home: Path,
    tmp_path: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test error message for unsupported format."""
    unsupported_file = tmp_path / "file.bmp"
    unsupported_file.write_bytes(b"fake bmp data")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--destination", str(dest_dir), str(unsupported_file)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    # New validation provides more accurate error message
    assert "not a valid image" in result.output


# ============================================================================
# 3. Source/Destination Validation
# ============================================================================


def test_fetch_exits_when_source_does_not_exist(
    runner: CliRunner,
    fake_home: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test exits with code 1 when source doesn't exist."""
    nonexistent_source = "/nonexistent/source/directory"

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", nonexistent_source, "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1


def test_fetch_error_message_mentions_source_directory(
    runner: CliRunner,
    fake_home: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test error message mentions source directory."""
    nonexistent_source = "/nonexistent/source/directory"

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", nonexistent_source, "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Source directory" in result.output
    assert "does not exist" in result.output


def test_fetch_exits_when_destination_does_not_exist(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test exits with code 1 when destination doesn't exist."""
    create_screenshot(source_dir, "screenshot.png")
    nonexistent_dest = "/nonexistent/dest/directory"

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", nonexistent_dest],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1


def test_fetch_error_message_mentions_destination_directory(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    config_file: Path,
) -> None:
    """Test error message mentions destination directory."""
    create_screenshot(source_dir, "screenshot.png")
    nonexistent_dest = "/nonexistent/dest/directory"

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", nonexistent_dest],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Destination directory" in result.output
    assert "does not exist" in result.output


# ============================================================================
# 4. Output Format Validation
# ============================================================================


def test_fetch_exits_for_invalid_output_format(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test exits with code 1 for invalid output format."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "invalid",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1


def test_fetch_case_insensitive_format_matching(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test case-insensitive format matching (HTML, html, Html all work)."""
    create_screenshot(source_dir, "screenshot.png")

    for format_variant in ["HTML", "html", "Html", "HtMl"]:
        result = runner.invoke(
            cli.wslshot,
            [
                "fetch",
                "--source",
                str(source_dir),
                "--destination",
                str(dest_dir),
                "--output-style",
                format_variant,
            ],
            env={"HOME": str(fake_home)},
        )

        assert result.exit_code == 0, f"Failed for format: {format_variant}"
        assert '<img src="' in result.output


def test_fetch_error_lists_valid_options(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test error lists valid options: markdown, html, text."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "xml",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "markdown" in result.output
    assert "html" in result.output
    assert "text" in result.output


def test_fetch_rejects_plain_text_cli_input(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test `--output-style plain_text` is rejected with error."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "plain_text",
        ],
        env={"HOME": str(fake_home)},
    )

    # Should fail with exit code 1
    assert result.exit_code == 1
    # Should show error message
    assert "Invalid output format" in result.output
    # Should list valid options
    assert "markdown" in result.output
    assert "html" in result.output
    assert "text" in result.output


def test_fetch_rejects_plain_text_in_config(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test config with `plain_text` format is rejected with error."""
    create_screenshot(source_dir, "screenshot.png")

    # Create config with legacy plain_text format
    config_data = {
        "default_source": str(source_dir),
        "default_destination": str(dest_dir),
        "default_output_format": "plain_text",
        "default_count": 1,
        "auto_stage_enabled": False,
        "default_convert_to": None,
    }
    with open(config_file, "w") as f:
        json.dump(config_data, f)

    result = runner.invoke(
        cli.wslshot,
        ["fetch"],
        env={"HOME": str(fake_home)},
    )

    # Should fail with exit code 1
    assert result.exit_code == 1
    # Should show error message
    assert "Invalid output format" in result.output
    # Should list valid options
    assert "markdown" in result.output
    assert "html" in result.output
    assert "text" in result.output


# ============================================================================
# 5. Git Integration
# ============================================================================


def test_fetch_stages_files_when_auto_stage_enabled_and_in_git_repo(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test stages files when auto_stage_enabled=True and in git repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    dest_dir = repo_root / "images"
    dest_dir.mkdir()

    create_screenshot(source_dir, "screenshot.png")

    # Enable auto-staging in config
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": True,
                "default_output_format": "markdown",
            }
        )
    )

    # Track git add calls
    git_add_calls = []

    def fake_subprocess_run(cmd, check=False, cwd=None, **kwargs):
        if cmd[:2] == ["git", "add"]:
            git_add_calls.append({"cmd": cmd, "cwd": cwd})
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: repo_root)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert len(git_add_calls) == 1
    assert git_add_calls[0]["cwd"] == repo_root


def test_fetch_skips_staging_when_auto_stage_disabled(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test skips staging when auto_stage_enabled=False."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    dest_dir = repo_root / "images"
    dest_dir.mkdir()

    create_screenshot(source_dir, "screenshot.png")

    # Disable auto-staging in config
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Track git add calls
    git_add_calls = []

    def fake_subprocess_run(cmd, check=False, cwd=None, **kwargs):
        if cmd[:2] == ["git", "add"]:
            git_add_calls.append({"cmd": cmd, "cwd": cwd})
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: repo_root)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert len(git_add_calls) == 0


def test_fetch_uses_relative_paths_when_in_git_repo(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test uses relative paths when in git repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    dest_dir = repo_root / "images"
    dest_dir.mkdir()

    create_screenshot(source_dir, "screenshot.png")

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: repo_root)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Relative paths should start with / when in git repo
    assert "](/images/screenshot_" in result.output or "](/images/animated_" in result.output


def test_fetch_uses_absolute_paths_when_not_in_git_repo(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test uses absolute paths when not in git repo."""
    create_screenshot(source_dir, "screenshot.png")

    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Absolute paths should contain the full destination directory
    assert str(dest_dir) in result.output


def test_fetch_skips_staging_when_destination_outside_repo(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test skips staging when destination is outside repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    dest_dir = tmp_path / "outside_repo"
    dest_dir.mkdir()

    create_screenshot(source_dir, "screenshot.png")

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": "",
                "auto_stage_enabled": True,
                "default_output_format": "markdown",
            }
        )
    )

    # Track git add calls
    git_add_calls = []

    def fake_subprocess_run(cmd, check=False, cwd=None, **kwargs):
        if cmd[:2] == ["git", "add"]:
            git_add_calls.append({"cmd": cmd, "cwd": cwd})
        return MagicMock(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: repo_root)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should not stage files outside the repo
    assert len(git_add_calls) == 0
    # Should use absolute paths since destination is outside repo
    assert str(dest_dir) in result.output


def test_fetch_handles_get_git_root_error_gracefully(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test handles get_git_root() RuntimeError gracefully."""
    create_screenshot(source_dir, "screenshot.png")

    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(
        cli, "get_git_root", lambda: (_ for _ in ()).throw(RuntimeError("Git root not found"))
    )

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    # Should still succeed but show error message
    assert result.exit_code == 0
    # Should fall back to absolute paths
    assert str(dest_dir) in result.output


# ============================================================================
# 6. Screenshot Fetching
# ============================================================================


def test_fetch_fetches_most_recent_screenshot(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetches most recent screenshot."""
    base_time = 1700000000
    old_screenshot = create_screenshot(source_dir, "old.png")
    os.utime(old_screenshot, (base_time, base_time))
    recent_screenshot = create_screenshot(source_dir, "recent.png")
    os.utime(recent_screenshot, (base_time + 2, base_time + 2))

    # Verify recent is actually newer
    assert recent_screenshot.stat().st_mtime > old_screenshot.stat().st_mtime

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should copy exactly one file (the most recent)
    copied_files = list(dest_dir.glob("screenshot_*.png"))
    assert len(copied_files) == 1


def test_fetch_fetches_n_most_recent_when_count_n(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetches N most recent when count=N."""
    base_time = 1700000000
    for i in range(5):
        screenshot = create_screenshot(source_dir, f"screenshot_{i}.png")
        timestamp = base_time + (i * 2)
        os.utime(screenshot, (timestamp, timestamp))

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir), "--count", "3"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should copy exactly 3 files
    copied_files = list(dest_dir.glob("screenshot_*.png"))
    assert len(copied_files) == 3


def test_fetch_exits_when_no_screenshots_found(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test exits when no screenshots found."""
    # Empty source directory

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "No screenshot found" in result.output


def test_fetch_exits_when_requested_count_exceeds_available(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test exits when requested count > available."""
    create_screenshot(source_dir, "screenshot1.png")
    create_screenshot(source_dir, "screenshot2.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir), "--count", "5"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "You requested 5 screenshot(s), but only 2 were found" in result.output


# ============================================================================
# 7. Output Verification
# ============================================================================


def test_fetch_stdout_contains_formatted_path(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test stdout contains formatted path."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert result.output.strip()  # Should have output
    assert "screenshot_" in result.output


def test_fetch_markdown_format_in_output(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test markdown format in output."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "markdown",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert result.output.startswith("![screenshot_")
    assert "](" in result.output


def test_fetch_html_format_in_output(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test HTML format in output."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "html",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert result.output.startswith("<img src=")
    assert 'alt="screenshot_' in result.output


def test_fetch_plain_text_format_in_output(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test text format in output."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--output-style",
            "text",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should contain the path, but no markdown or HTML formatting
    assert str(dest_dir) in result.output
    assert "![" not in result.output
    assert "<img" not in result.output


def test_fetch_exit_code_0_on_success(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test exit code 0 on success."""
    create_screenshot(source_dir, "screenshot.png")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0


# ============================================================================
# 8. Image Format Conversion Tests
# ============================================================================


def create_real_image(directory: Path, name: str, format: str = "PNG") -> Path:
    """Create a real image file that can be opened by PIL."""
    from PIL import Image

    screenshot = directory / name
    img = Image.new("RGB", (100, 100), color="red")
    img.save(screenshot, format)
    return screenshot


def test_fetch_with_convert_to_jpg(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with --convert-to jpg option."""
    create_real_image(source_dir, "screenshot.png", "PNG")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--convert-to",
            "jpg",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Verify JPG file was created in destination
    jpg_files = list(dest_dir.glob("*.jpg"))
    assert len(jpg_files) == 1
    # Verify PNG file was removed (original deleted after conversion)
    png_files = list(dest_dir.glob("*.png"))
    assert len(png_files) == 0
    # Verify output shows JPG extension
    assert ".jpg" in result.output


def test_fetch_with_convert_to_short_flag(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with -c short flag for conversion."""
    create_real_image(source_dir, "screenshot.png", "PNG")

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--source", str(source_dir), "--destination", str(dest_dir), "-c", "webp"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    webp_files = list(dest_dir.glob("*.webp"))
    assert len(webp_files) == 1


def test_fetch_convert_to_invalid_format(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test fetch with invalid conversion format shows error."""
    create_real_image(source_dir, "screenshot.png", "PNG")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--convert-to",
            "bmp",
        ],
        env={"HOME": str(fake_home)},
    )

    # Click validates the choice before our code runs
    assert result.exit_code != 0
    assert "Invalid value for '--convert-to'" in result.output


def test_fetch_convert_to_removes_original(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test that conversion removes the original file."""
    create_real_image(source_dir, "test.jpg", "JPEG")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--convert-to",
            "png",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Original JPG should be removed from destination
    jpg_files = list(dest_dir.glob("*.jpg"))
    assert len(jpg_files) == 0
    # PNG should exist
    png_files = list(dest_dir.glob("*.png"))
    assert len(png_files) == 1


def test_fetch_convert_to_with_git_staging(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that conversion works with git auto-staging."""
    # Enable auto-staging in config
    config_file.write_text(
        json.dumps(
            {
                "default_source": str(source_dir),
                "default_destination": str(dest_dir),
                "auto_stage_enabled": True,
                "default_output_format": "markdown",
                "default_convert_to": None,
            }
        )
    )

    create_real_image(source_dir, "screenshot.png", "PNG")

    # Mock git operations
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: dest_dir)

    staged_files = []

    def mock_stage(screenshots, git_root):
        staged_files.extend(screenshots)

    monkeypatch.setattr(cli, "stage_screenshots", mock_stage)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--convert-to", "jpg"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Verify converted file (JPG) was staged, not original PNG
    assert len(staged_files) == 1
    assert staged_files[0].suffix == ".jpg"


def test_fetch_config_default_convert_to(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that config default_convert_to is used when no CLI option provided."""
    # Update config with default_convert_to
    config_file.write_text(
        json.dumps(
            {
                "default_source": str(source_dir),
                "default_destination": str(dest_dir),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
                "default_convert_to": "webp",
            }
        )
    )

    create_real_image(source_dir, "screenshot.png", "PNG")

    # Mock git detection to use config destination
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = runner.invoke(
        cli.wslshot,
        ["fetch"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Verify WebP file was created (from config default)
    webp_files = list(dest_dir.glob("*.webp"))
    assert len(webp_files) == 1


def test_fetch_convert_to_cli_overrides_config(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CLI --convert-to overrides config default_convert_to."""
    # Update config with default_convert_to
    config_file.write_text(
        json.dumps(
            {
                "default_source": str(source_dir),
                "default_destination": str(dest_dir),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
                "default_convert_to": "webp",
            }
        )
    )

    create_real_image(source_dir, "screenshot.png", "PNG")

    # Mock git detection to use config destination
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = runner.invoke(
        cli.wslshot,
        ["fetch", "--convert-to", "jpg"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # CLI option (jpg) should override config (webp)
    jpg_files = list(dest_dir.glob("*.jpg"))
    assert len(jpg_files) == 1
    webp_files = list(dest_dir.glob("*.webp"))
    assert len(webp_files) == 0


def test_fetch_convert_to_output_path_correct(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test that output shows correct path with converted extension."""
    create_real_image(source_dir, "test.png", "PNG")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--convert-to",
            "jpg",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Output should show .jpg extension, not .png
    assert ".jpg" in result.output
    assert "screenshot_" in result.output


def test_fetch_convert_to_no_conversion_when_same_format(
    runner: CliRunner,
    fake_home: Path,
    source_dir: Path,
    dest_dir: Path,
    config_file: Path,
) -> None:
    """Test that no conversion happens when already in target format."""
    create_real_image(source_dir, "screenshot.png", "PNG")

    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--convert-to",
            "png",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Should still have PNG file (no conversion needed)
    png_files = list(dest_dir.glob("*.png"))
    assert len(png_files) == 1
