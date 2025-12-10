from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from wslshot import cli


def write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_migrate_config_updates_plain_text(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "plain_text"})

    result = cli.migrate_config(config_path)

    assert result["migrated"] is True
    assert "default_output_format: 'plain_text' → 'text'" in result["changes"]
    updated = json.loads(config_path.read_text())
    assert updated["default_output_format"] == "text"


def test_migrate_config_updates_plain_text_case_insensitive(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "Plain_Text"})

    result = cli.migrate_config(config_path)

    assert result["migrated"] is True
    assert "default_output_format: 'plain_text' → 'text'" in result["changes"]
    updated = json.loads(config_path.read_text())
    assert updated["default_output_format"] == "text"


def test_migrate_config_dry_run_preview(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "plain_text"})

    result = cli.migrate_config(config_path, dry_run=True)

    assert result["migrated"] is False
    assert result["changes"] == ["default_output_format: 'plain_text' → 'text'"]
    # Preview should show the migrated value while leaving the file unchanged
    assert result["config"]["default_output_format"] == "text"
    unchanged = json.loads(config_path.read_text())
    assert unchanged["default_output_format"] == "plain_text"


def test_migrate_config_no_changes_when_up_to_date(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "text"})

    result = cli.migrate_config(config_path)

    assert result["migrated"] is False
    assert result["changes"] == []
    updated = json.loads(config_path.read_text())
    assert updated["default_output_format"] == "text"


def test_migrate_config_missing_file_returns_error(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    if config_path.exists():
        config_path.unlink()

    result = cli.migrate_config(config_path)

    assert result["migrated"] is False
    assert result["changes"] == []
    assert "error" in result
    assert "<...>/config.json" in result["error"]
    assert str(config_path) not in result["error"]
    assert not config_path.exists()


def test_migrate_config_malformed_json(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{invalid json")

    result = cli.migrate_config(config_path)

    assert result["migrated"] is False
    assert "error" in result
    assert "Cannot read config" in result["error"]


def test_migrate_config_command_dry_run(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "plain_text"})

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["migrate-config", "--dry-run"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "dry-run" in result.output
    assert "[would change]" in result.output
    stored = json.loads(config_path.read_text())
    assert stored["default_output_format"] == "plain_text"


def test_migrate_config_command_applies_changes(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    write_config(config_path, {"default_output_format": "plain_text"})

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["migrate-config"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "Applied changes:" in result.output
    updated = json.loads(config_path.read_text())
    assert updated["default_output_format"] == "text"


def test_migrate_config_command_handles_missing_config(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    if config_path.exists():
        config_path.unlink()

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["migrate-config"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert "No config file found" in result.output
    assert not config_path.exists()


def test_migrate_config_invalid_json_type(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("[]")  # Array instead of object

    result = cli.migrate_config(config_path)

    assert result["migrated"] is False
    assert "error" in result
    assert "Invalid config format" in result["error"]


def test_migrate_config_cli_invalid_json_type(fake_home: Path) -> None:
    config_path = fake_home / ".config" / "wslshot" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('""')  # String instead of object

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        ["migrate-config"],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Invalid config format" in result.output
