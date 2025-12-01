from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from wslshot import cli


def create_default_config(config_file: Path) -> None:
    """Helper to create a default config file."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
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


def test_configure_source_with_valid_directory(fake_home: Path, tmp_path: Path) -> None:
    """Test configure --source updates config with valid directory."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--source", str(source_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_source"] == str(source_dir)
    # Verify other fields were preserved
    assert updated_config["default_destination"] == ""
    assert updated_config["auto_stage_enabled"] is False
    assert updated_config["default_output_format"] == "markdown"


def test_configure_source_with_invalid_directory(fake_home: Path) -> None:
    """Test configure --source exits with error for invalid directory."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--source", "/nonexistent/path"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Invalid source directory" in result.output


def test_configure_destination_with_valid_directory(fake_home: Path, tmp_path: Path) -> None:
    """Test configure --destination updates config with valid directory."""
    dest_dir = tmp_path / "output"
    dest_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_destination"] == str(dest_dir)
    # Verify other fields were preserved
    assert updated_config["default_source"] == ""
    assert updated_config["auto_stage_enabled"] is False
    assert updated_config["default_output_format"] == "markdown"


def test_configure_destination_with_invalid_directory(fake_home: Path) -> None:
    """Test configure --destination exits with error for invalid directory."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--destination", "/nonexistent/path"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Invalid destination directory" in result.output


def test_configure_auto_stage_enabled_true(fake_home: Path) -> None:
    """Test configure --auto-stage-enabled True updates config."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--auto-stage-enabled", "True"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["auto_stage_enabled"] is True
    # Verify other fields were preserved
    assert updated_config["default_source"] == ""
    assert updated_config["default_destination"] == ""
    assert updated_config["default_output_format"] == "markdown"


def test_configure_auto_stage_enabled_false(fake_home: Path) -> None:
    """Test configure --auto-stage-enabled False updates config."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
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

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--auto-stage-enabled", "False"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["auto_stage_enabled"] is False


def test_configure_output_format_markdown(fake_home: Path) -> None:
    """Test configure --output-style markdown updates config."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "markdown"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "markdown"


def test_configure_output_format_html(fake_home: Path) -> None:
    """Test configure --output-style html updates config."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "html"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "html"


def test_configure_output_format_plain_text(fake_home: Path) -> None:
    """Test configure --output-style text updates config."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "text"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "text"


def test_configure_output_format_case_insensitive(fake_home: Path) -> None:
    """Test configure --output-style accepts case-insensitive values."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "HTML"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated with lowercase value
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "html"


def test_configure_output_format_with_invalid_value(fake_home: Path) -> None:
    """Test configure --output-style exits with error for invalid value."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "invalid"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Invalid output format" in result.output
    assert "markdown, html, text" in result.output


@pytest.mark.parametrize(
    ("user_input", "expected_suggestion"),
    [
        ("markdwon", "Did you mean: markdown?"),
        ("HTM", "Did you mean: html?"),
    ],
)
def test_configure_output_format_suggests_closest_match(
    fake_home: Path,
    user_input: str,
    expected_suggestion: str,
) -> None:
    """Test configure prints suggestion for near-miss output styles."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", user_input],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Invalid output format" in result.output
    assert expected_suggestion in result.output


def test_configure_with_multiple_options(fake_home: Path, tmp_path: Path) -> None:
    """Test configure with multiple options at once."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()
    dest_dir = tmp_path / "output"
    dest_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        [
            "configure",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify both configs were updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_source"] == str(source_dir)
    assert updated_config["default_destination"] == str(dest_dir)
    # Verify other fields were preserved
    assert updated_config["auto_stage_enabled"] is False
    assert updated_config["default_output_format"] == "markdown"


def test_configure_with_all_options(fake_home: Path, tmp_path: Path) -> None:
    """Test configure with all four options together."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()
    dest_dir = tmp_path / "output"
    dest_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        [
            "configure",
            "--source",
            str(source_dir),
            "--destination",
            str(dest_dir),
            "--auto-stage-enabled",
            "True",
            "--output-style",
            "html",
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify all configs were updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_source"] == str(source_dir)
    assert updated_config["default_destination"] == str(dest_dir)
    assert updated_config["auto_stage_enabled"] is True
    assert updated_config["default_output_format"] == "html"


def test_configure_no_options_triggers_write_config(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test configure with no options calls write_config()."""
    write_config_called: list[Path] = []

    def mock_write_config(path: Path) -> None:
        write_config_called.append(path)

    monkeypatch.setattr(cli, "write_config", mock_write_config)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert len(write_config_called) == 1
    assert write_config_called[0] == fake_home / ".config" / "wslshot" / "config.json"


def test_configure_updates_preserve_other_fields(fake_home: Path, tmp_path: Path) -> None:
    """Test updating one option preserves others."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()
    dest_dir = tmp_path / "output"
    dest_dir.mkdir()

    # Create config with all fields set
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(
            {
                "default_source": str(source_dir),
                "default_destination": str(dest_dir),
                "auto_stage_enabled": True,
                "default_output_format": "html",
            }
        )
    )

    # Update only output format
    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "markdown"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify only output format changed
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_source"] == str(source_dir)
    assert updated_config["default_destination"] == str(dest_dir)
    assert updated_config["auto_stage_enabled"] is True
    assert updated_config["default_output_format"] == "markdown"


def test_configure_creates_config_file_if_missing(fake_home: Path, tmp_path: Path) -> None:
    """Test configure creates config file if it doesn't exist."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    # Ensure config file doesn't exist
    assert not config_file.exists()

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--source", str(source_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    # Config file should now exist
    assert config_file.exists()
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_source"] == str(source_dir)


def test_configure_source_resolves_to_absolute_path(fake_home: Path, tmp_path: Path) -> None:
    """Test configure --source resolves relative paths to absolute."""
    source_dir = tmp_path / "screenshots"
    source_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    # Use the absolute path
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--source", str(source_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config contains absolute path
    updated_config = json.loads(config_file.read_text())
    assert Path(updated_config["default_source"]).is_absolute()
    assert updated_config["default_source"] == str(source_dir)


def test_configure_destination_resolves_to_absolute_path(fake_home: Path, tmp_path: Path) -> None:
    """Test configure --destination resolves paths to absolute."""
    dest_dir = tmp_path / "output"
    dest_dir.mkdir()

    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--destination", str(dest_dir)],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config contains absolute path
    updated_config = json.loads(config_file.read_text())
    assert Path(updated_config["default_destination"]).is_absolute()
    assert updated_config["default_destination"] == str(dest_dir)


def test_configure_convert_to_sets_default(fake_home: Path) -> None:
    """Test configure --convert-to sets the default conversion format."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--convert-to", "jpg"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated with convert format
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_convert_to"] == "jpg"


def test_configure_convert_to_invalid_format(fake_home: Path) -> None:
    """Test configure --convert-to with invalid format shows error."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--convert-to", "bmp"],
        env={"HOME": str(fake_home)},
    )

    # Click validates the choice before our code runs
    assert result.exit_code != 0
    assert "Invalid value for '--convert-to'" in result.output


def test_configure_with_output_style_markdown(fake_home: Path) -> None:
    """Test configure --output-style markdown (new option name)."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "markdown"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "markdown"


def test_configure_with_output_style_html(fake_home: Path) -> None:
    """Test configure --output-style html (new option name)."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "html"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "html"


def test_configure_with_output_style_text(fake_home: Path) -> None:
    """Test configure --output-style text (new option name)."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "text"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    # Verify config was updated
    updated_config = json.loads(config_file.read_text())
    assert updated_config["default_output_format"] == "text"


def test_configure_output_style_no_deprecation_warning(fake_home: Path) -> None:
    """Test that using --output-style does NOT show a deprecation warning."""
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    create_default_config(config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["configure", "--output-style", "markdown"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0

    warning_output = result.stderr or result.output

    # Should NOT show deprecation warnings
    assert "--output-format" not in warning_output
    assert "deprecated" not in warning_output
