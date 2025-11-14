"""
Tests for plain_text deprecation fixes.

These tests verify:
1. Deprecation warning is visible to users
2. Interactive config normalizes plain_text to text
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from wslshot import cli


def test_plain_text_deprecation_warning_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that plain_text deprecation warning is visible to users."""
    # Create a fake config directory with valid config
    config_dir = tmp_path / ".config" / "wslshot"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    # Create source directory for the test
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    # Create a test screenshot
    screenshot = source_dir / "test_screenshot.png"
    screenshot.touch()

    # Create valid config
    config = {
        "default_source": str(source_dir),
        "default_destination": str(tmp_path),
        "auto_stage_enabled": False,
        "default_output_format": "markdown",
        "default_convert_to": None,
    }
    config_file.write_text(json.dumps(config))

    # Capture stderr output
    stderr_output = []

    def mock_echo(msg, err=False, **kwargs):
        if err:
            stderr_output.append(msg)

    monkeypatch.setattr("click.echo", mock_echo)

    # Run the command with plain_text format
    # Use isolated filesystem to avoid creating files in repo
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.wslshot,
            ["fetch", "--output-format", "plain_text", "--destination", str(tmp_path)],
            env={"HOME": str(tmp_path)},
            catch_exceptions=False,
        )

    # Check that warning appears in our captured stderr
    stderr_text = " ".join(stderr_output)
    assert "deprecated" in stderr_text.lower()
    assert "plain_text" in stderr_text.lower()
    assert "text" in stderr_text.lower()
    assert "Warning:" in stderr_text  # Check for our visible warning prefix

    # Also check that the command still works (exit code 0)
    assert result.exit_code == 0


def test_plain_text_deprecation_warning_visible_output_style(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that plain_text deprecation warning is visible when using --output-style (primary interface)."""
    # Create a fake config directory with valid config
    config_dir = tmp_path / ".config" / "wslshot"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    # Create source directory for the test
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    # Create a test screenshot
    screenshot = source_dir / "test_screenshot.png"
    screenshot.touch()

    # Create valid config
    config = {
        "default_source": str(source_dir),
        "default_destination": str(tmp_path),
        "auto_stage_enabled": False,
        "default_output_format": "markdown",
        "default_convert_to": None,
    }
    config_file.write_text(json.dumps(config))

    # Capture stderr output
    stderr_output = []

    def mock_echo(msg, err=False, **kwargs):
        if err:
            stderr_output.append(msg)

    monkeypatch.setattr("click.echo", mock_echo)

    # Run the command with plain_text format using --output-style (the primary interface)
    # Use isolated filesystem to avoid creating files in repo
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.wslshot,
            ["fetch", "--output-style", "plain_text", "--destination", str(tmp_path)],
            env={"HOME": str(tmp_path)},
            catch_exceptions=False,
        )

    # Check that warning appears in our captured stderr
    stderr_text = " ".join(stderr_output)
    assert "deprecated" in stderr_text.lower()
    assert "plain_text" in stderr_text.lower()
    assert "text" in stderr_text.lower()
    assert "Warning:" in stderr_text  # Check for our visible warning prefix

    # Also check that the command still works (exit code 0)
    assert result.exit_code == 0


def test_interactive_config_normalizes_plain_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that interactive configure normalizes plain_text to text."""
    # Create a fake config directory
    config_dir = tmp_path / ".config" / "wslshot"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    # Create source/dest directories
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Create initial config with plain_text
    initial_config = {
        "default_source": str(source_dir),
        "default_destination": str(dest_dir),
        "auto_stage_enabled": False,
        "default_output_format": "plain_text",  # Old deprecated value
        "default_convert_to": None,
    }
    config_file.write_text(json.dumps(initial_config))

    # Mock click.prompt to return default values (simulating pressing Enter)
    def mock_prompt(text, default=None, **kwargs):
        # Return the default value (simulating user pressing Enter)
        return default if default is not None else ""

    monkeypatch.setattr("click.prompt", mock_prompt)

    # Mock click.confirm to return False (N) for boolean prompts
    monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

    # Also need to mock click.echo to avoid output during test
    monkeypatch.setattr("click.echo", lambda *args, **kwargs: None)

    # Run interactive config
    cli.write_config(config_file)

    # Read the resulting config
    saved_config = json.loads(config_file.read_text())

    # Verify plain_text was normalized to text
    assert saved_config["default_output_format"] == "text", "plain_text should be normalized to text"

    # Verify other fields unchanged
    assert saved_config["default_source"] == str(source_dir)
    assert saved_config["default_destination"] == str(dest_dir)
    assert saved_config["auto_stage_enabled"] is False
    assert saved_config["default_convert_to"] is None


def test_configure_command_with_plain_text_normalizes(tmp_path: Path) -> None:
    """Test that configure command with --output-format plain_text normalizes to text."""
    # Create config directory
    config_dir = tmp_path / ".config" / "wslshot"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    # Create source directory
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    # Run configure command with plain_text
    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-format", "plain_text"],
        env={"HOME": str(tmp_path)},
        catch_exceptions=False,
    )

    # Should succeed
    assert result.exit_code == 0

    # Read saved config
    saved_config = json.loads(config_file.read_text())

    # Verify plain_text was normalized to text
    assert saved_config["default_output_format"] == "text", "plain_text should be normalized to text"


def test_fetch_with_plain_text_from_config_shows_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that using plain_text from config file also shows deprecation warning."""
    # Create a fake config directory with plain_text in config
    config_dir = tmp_path / ".config" / "wslshot"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    # Create source directory for the test
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    # Create a test screenshot
    screenshot = source_dir / "test_screenshot.png"
    screenshot.touch()

    # Create config with plain_text as default
    config = {
        "default_source": str(source_dir),
        "default_destination": str(tmp_path),
        "auto_stage_enabled": False,
        "default_output_format": "plain_text",  # Deprecated value in config
        "default_convert_to": None,
    }
    config_file.write_text(json.dumps(config))

    # Capture stderr output
    stderr_output = []

    def mock_echo(msg, err=False, **kwargs):
        if err:
            stderr_output.append(msg)

    monkeypatch.setattr("click.echo", mock_echo)

    # Run fetch without specifying output format (uses config default)
    # Use isolated filesystem to avoid creating files in repo
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli.wslshot,
            ["fetch", "--destination", str(tmp_path)],
            env={"HOME": str(tmp_path)},
            catch_exceptions=False,
        )

    # Check that warning appears in our captured stderr
    stderr_text = " ".join(stderr_output)
    assert "deprecated" in stderr_text.lower()
    assert "plain_text" in stderr_text.lower()
    assert "text" in stderr_text.lower()
    assert "Warning:" in stderr_text

    # Command should still work
    assert result.exit_code == 0