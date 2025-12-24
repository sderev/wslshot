from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import click
import pytest

from wslshot import cli
from wslshot.exceptions import ConfigurationError, SecurityError, ValidationError


class TestGetConfigFilePath:
    """Tests for get_config_file_path() function."""

    def test_get_config_file_path_creates_correct_path(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that config file is created at ~/.config/wslshot/config.json."""

        # Mock write_config to avoid interactive prompts
        def mock_write_config(path: Path) -> None:
            with open(path, "w", encoding="UTF-8") as f:
                json.dump({}, f)

        monkeypatch.setattr(cli, "write_config", mock_write_config)

        config_path = cli.get_config_file_path()
        expected_path = fake_home / ".config" / "wslshot" / "config.json"
        assert config_path == expected_path

    def test_get_config_file_path_creates_parent_directories(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that parent directories are created if they don't exist."""
        # Remove the config directory to test creation
        config_dir = fake_home / ".config" / "wslshot"
        if config_dir.exists():
            import shutil

            shutil.rmtree(config_dir)

        # Mock write_config to avoid interactive prompts
        def mock_write_config(path: Path) -> None:
            with open(path, "w", encoding="UTF-8") as f:
                json.dump({}, f)

        monkeypatch.setattr(cli, "write_config", mock_write_config)

        config_path = cli.get_config_file_path()
        assert config_path.parent.exists()
        assert config_path.parent.is_dir()

    def test_get_config_file_path_creates_file_if_not_exists(self, fake_home: Path) -> None:
        """Test that config file is created if it doesn't exist."""
        config_path = cli.get_config_file_path()

        assert config_path.exists()

        # Verify default config was written
        with open(config_path, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_source"] == ""
        assert config["default_destination"] == ""
        assert config["auto_stage_enabled"] is False
        assert config["default_output_format"] == "markdown"

    def test_get_config_file_path_sets_restrictive_permissions(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that config file is created with 0o600 permissions."""

        # Mock write_config to avoid interactive prompts
        def mock_write_config(path: Path) -> None:
            with open(path, "w", encoding="UTF-8") as f:
                json.dump({}, f)

        monkeypatch.setattr(cli, "write_config", mock_write_config)

        config_path = cli.get_config_file_path()
        # Check file permissions (mode & 0o777 to get just permission bits)
        assert (config_path.stat().st_mode & 0o777) == 0o600


class TestReadConfig:
    """Tests for read_config() function."""

    def test_read_config_with_valid_json(self, fake_home: Path, tmp_path: Path) -> None:
        """Test reading a valid JSON configuration file."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"

        # Create directories so paths are valid
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        config_data = {
            "default_source": str(source_dir),
            "default_destination": str(dest_dir),
            "auto_stage_enabled": True,
            "default_output_format": "html",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(config_data, f)

        result = cli.read_config(config_file)

        # Validation normalizes paths and fills missing defaults
        assert result["default_source"] == str(source_dir.resolve())
        assert result["default_destination"] == str(dest_dir.resolve())
        assert result["auto_stage_enabled"] is True
        assert result["default_output_format"] == "html"
        # Missing fields are filled with defaults
        assert result["default_convert_to"] is None
        assert result["max_file_size_mb"] == 50
        assert result["max_total_size_mb"] == 200

    def test_read_config_with_empty_file_non_interactive_replaces_with_defaults(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that non-interactive runs recover from JSONDecodeError without prompting."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text("")  # Empty file causes JSONDecodeError

        monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)
        monkeypatch.setattr(
            cli, "write_config", lambda _path: pytest.fail("write_config() was called")
        )

        result = cli.read_config(config_file)

        assert result == cli.DEFAULT_CONFIG
        assert json.loads(config_file.read_text(encoding="UTF-8")) == cli.DEFAULT_CONFIG

        backup_file = config_file.with_name(f"{config_file.name}.corrupted")
        assert backup_file.exists()
        assert backup_file.read_text(encoding="UTF-8") == ""

    def test_read_config_with_existing_corrupted_backup_uses_next_suffix(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that backups never overwrite existing `.corrupted` files."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        existing_backup = config_file.with_name(f"{config_file.name}.corrupted")
        existing_backup.write_text("previous backup", encoding="UTF-8")

        corrupted_contents = '{"invalid": json content}'
        config_file.write_text(corrupted_contents, encoding="UTF-8")

        monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)
        monkeypatch.setattr(
            cli, "write_config", lambda _path: pytest.fail("write_config() was called")
        )

        result = cli.read_config(config_file)
        assert result == cli.DEFAULT_CONFIG
        assert json.loads(config_file.read_text(encoding="UTF-8")) == cli.DEFAULT_CONFIG

        assert existing_backup.read_text(encoding="UTF-8") == "previous backup"

        backup_file = config_file.with_name(f"{config_file.name}.corrupted.1")
        assert backup_file.exists()
        assert backup_file.read_text(encoding="UTF-8") == corrupted_contents

    def test_read_config_with_corrupted_json_triggers_write(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that corrupted JSON triggers write_config."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        corrupted_contents = '{"invalid": json content}'
        config_file.write_text(corrupted_contents)

        monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: True)

        write_config_called = []

        def mock_write_config(path: Path) -> None:
            write_config_called.append(path)
            with open(path, "w", encoding="UTF-8") as f:
                json.dump({"recovered": True}, f)

        monkeypatch.setattr(cli, "write_config", mock_write_config)

        result = cli.read_config(config_file)
        assert write_config_called == [config_file]
        assert result == {"recovered": True}

        backup_file = config_file.with_name(f"{config_file.name}.corrupted")
        assert backup_file.exists()
        assert backup_file.read_text(encoding="UTF-8") == corrupted_contents


class TestWriteConfig:
    """Tests for write_config() function."""

    def test_write_config_creates_new_config_with_defaults(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that write_config creates a new configuration file with defaults."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"

        # Create test directories
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        # Mock user input
        inputs = {
            "default_source": str(source_dir),
            "default_destination": str(dest_dir),
            "auto_stage_enabled": True,
            "default_output_format": "html",
            "default_convert_to": None,
        }

        def mock_get_validated_directory_input(
            field: str, message: str, current_config: dict[str, Any], default: str
        ) -> str:
            return inputs[field]

        def mock_get_config_boolean_input(
            field: str, message: str, current_config: dict[str, Any], default: bool
        ) -> bool:
            return inputs[field]

        def mock_get_validated_input(
            field: str,
            message: str,
            current_config: dict[str, Any],
            default: str,
            options: list[str] | None = None,
        ) -> str:
            return inputs[field]

        def mock_get_config_input(
            field: str, message: str, current_config: dict[str, Any], default: str = ""
        ) -> str:
            value = inputs.get(field, "")
            return str(value) if value is not None else ""

        monkeypatch.setattr(
            cli, "get_validated_directory_input", mock_get_validated_directory_input
        )
        monkeypatch.setattr(cli, "get_config_boolean_input", mock_get_config_boolean_input)
        monkeypatch.setattr(cli, "get_validated_input", mock_get_validated_input)
        monkeypatch.setattr(cli, "get_config_input", mock_get_config_input)

        # Mock click.echo to suppress output (can be called with or without msg)
        monkeypatch.setattr("click.echo", lambda msg=None, **kwargs: None)
        monkeypatch.setattr("click.secho", lambda msg=None, **kwargs: None)

        cli.write_config(config_file)

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_source"] == str(source_dir)
        assert config["default_destination"] == str(dest_dir)
        assert config["auto_stage_enabled"] is True
        assert config["default_output_format"] == "html"

    def test_write_config_updates_existing_config(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that write_config updates an existing configuration file."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"

        # Create initial config
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        initial_config = {
            "default_source": str(source_dir),
            "default_destination": str(dest_dir),
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        # Mock user input to change settings
        new_dest_dir = tmp_path / "new_dest"
        new_dest_dir.mkdir()

        def mock_get_validated_directory_input(
            field: str, message: str, current_config: dict[str, Any], default: str
        ) -> str:
            if field == "default_destination":
                return str(new_dest_dir)
            return current_config.get(field, default)

        def mock_get_config_boolean_input(
            field: str, message: str, current_config: dict[str, Any], default: bool
        ) -> bool:
            return True  # Changed to True

        def mock_get_validated_input(
            field: str,
            message: str,
            current_config: dict[str, Any],
            default: str,
            options: list[str] | None = None,
        ) -> str:
            return current_config.get(field, default)

        def mock_get_config_input(
            field: str, message: str, current_config: dict[str, Any], default: str = ""
        ) -> str:
            value = current_config.get(field, "")
            return str(value) if value is not None else ""

        monkeypatch.setattr(
            cli, "get_validated_directory_input", mock_get_validated_directory_input
        )
        monkeypatch.setattr(cli, "get_config_boolean_input", mock_get_config_boolean_input)
        monkeypatch.setattr(cli, "get_validated_input", mock_get_validated_input)
        monkeypatch.setattr(cli, "get_config_input", mock_get_config_input)
        monkeypatch.setattr("click.echo", lambda msg=None, **kwargs: None)
        monkeypatch.setattr("click.secho", lambda msg=None, **kwargs: None)

        cli.write_config(config_file)

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_destination"] == str(new_dest_dir)
        assert config["auto_stage_enabled"] is True

    def test_write_config_maintains_permissions(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that write_config maintains 0o600 permissions after update."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.touch(mode=0o600)

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Mock all input functions
        def mock_input(*args: Any, **kwargs: Any) -> str:
            return str(source_dir)

        def mock_bool_input(*args: Any, **kwargs: Any) -> bool:
            return False

        monkeypatch.setattr(cli, "get_validated_directory_input", mock_input)
        monkeypatch.setattr(cli, "get_config_boolean_input", mock_bool_input)
        monkeypatch.setattr(cli, "get_validated_input", lambda *args, **kwargs: "markdown")
        monkeypatch.setattr(cli, "get_config_input", lambda *args, **kwargs: "")
        monkeypatch.setattr("click.echo", lambda msg=None, **kwargs: None)
        monkeypatch.setattr("click.secho", lambda msg=None, **kwargs: None)

        cli.write_config(config_file)

        # Permissions should still be 0o600
        assert (config_file.stat().st_mode & 0o777) == 0o600


class TestUpdateConfigField:
    """Tests for update_config_field() function."""

    def test_update_config_field_validates_field_name(self) -> None:
        """Test that invalid field names are rejected."""
        with pytest.raises(click.ClickException, match="Unknown config field"):
            cli.update_config_field("invalid_field", "value")

    def test_update_config_field_preserves_other_fields(self, fake_home: Path) -> None:
        """Test that updating one field doesn't affect others."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "/some/source",
            "default_destination": "/some/destination",
            "auto_stage_enabled": True,
            "default_output_format": "html",
            "default_convert_to": "png",
        }
        config_file.write_text(json.dumps(initial_config), encoding="UTF-8")
        config_file.chmod(0o600)

        cli.update_config_field("auto_stage_enabled", False)

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["auto_stage_enabled"] is False
        assert config["default_source"] == initial_config["default_source"]
        assert config["default_destination"] == initial_config["default_destination"]
        assert config["default_output_format"] == initial_config["default_output_format"]
        assert config["default_convert_to"] == initial_config["default_convert_to"]

    def test_update_config_field_preserves_permissions(self, fake_home: Path) -> None:
        """Test that update_config_field maintains 0o600 permissions after update."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "/some/source",
            "default_destination": "/some/destination",
            "auto_stage_enabled": True,
            "default_output_format": "html",
            "default_convert_to": "png",
        }
        config_file.write_text(json.dumps(initial_config), encoding="UTF-8")
        config_file.chmod(0o600)

        cli.update_config_field("auto_stage_enabled", False)

        assert (config_file.stat().st_mode & 0o777) == 0o600

    def test_update_config_field_normalizes_output_format(self, fake_home: Path) -> None:
        """Test that update_config_field normalizes output format values."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text(json.dumps({"default_output_format": "markdown"}), encoding="UTF-8")
        config_file.chmod(0o600)

        cli.update_config_field("default_output_format", "HTML")

        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_output_format"] == "html"

    def test_update_config_field_rejects_invalid_value(self) -> None:
        """Test that invalid config values are rejected."""
        with pytest.raises(click.ClickException, match="Invalid value for default_output_format"):
            cli.update_config_field("default_output_format", "not-a-format")

    def test_update_config_field_normalizes_convert_to(self, fake_home: Path) -> None:
        """Test that update_config_field normalizes `default_convert_to` values."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text("{}", encoding="UTF-8")
        config_file.chmod(0o600)

        cli.update_config_field("default_convert_to", "WEBP")
        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_convert_to"] == "webp"

        cli.update_config_field("default_convert_to", "")
        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_convert_to"] is None

    def test_update_config_field_rejects_invalid_convert_to(self) -> None:
        """Test that update_config_field rejects invalid conversion formats."""
        with pytest.raises(click.ClickException, match="Invalid value for default_convert_to"):
            cli.update_config_field("default_convert_to", "tiff")

    def test_update_config_field_validates_directory(self, fake_home: Path, tmp_path: Path) -> None:
        """Test that update_config_field validates directory paths."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text("{}", encoding="UTF-8")
        config_file.chmod(0o600)

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        cli.update_config_field("default_source", str(source_dir))
        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_source"] == str(source_dir.resolve())

        with pytest.raises(click.ClickException, match="Invalid value for default_source"):
            cli.update_config_field("default_source", str(tmp_path / "missing"))


class TestSetDefaultSource:
    """Tests for set_default_source() function."""

    def test_set_default_source_with_valid_directory(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test setting default source with a valid directory."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        cli.set_default_source(str(source_dir))

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_source"] == str(source_dir.resolve())

    def test_set_default_source_with_invalid_directory_raises_error(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_default_source raises ConfigurationError for invalid directory."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text("{}")

        invalid_dir = tmp_path / "nonexistent"

        with pytest.raises(ConfigurationError, match="Invalid source directory"):
            cli.set_default_source(str(invalid_dir))

    def test_set_default_source_preserves_other_config_fields(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """Test that set_default_source preserves other configuration fields."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "/some/path",
            "auto_stage_enabled": True,
            "default_output_format": "html",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        cli.set_default_source(str(source_dir))

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_destination"] == "/some/path"
        assert config["auto_stage_enabled"] is True
        assert config["default_output_format"] == "html"

    def test_set_default_source_allows_blank_to_clear(self, fake_home: Path) -> None:
        """Test that set_default_source can clear the configured value with blank input."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "/some/source",
            "default_destination": "/some/path",
            "auto_stage_enabled": True,
            "default_output_format": "html",
        }

        config_file.write_text(json.dumps(initial_config), encoding="UTF-8")

        cli.set_default_source("   ")

        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_source"] == ""
        assert config["default_destination"] == initial_config["default_destination"]
        assert config["auto_stage_enabled"] == initial_config["auto_stage_enabled"]
        assert config["default_output_format"] == initial_config["default_output_format"]

    def test_set_default_source_with_symlink_raises_security_error(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """set_default_source raises SecurityError for symlink paths."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "default_source": "",
                    "default_destination": "",
                    "auto_stage_enabled": False,
                    "default_output_format": "markdown",
                    "default_convert_to": None,
                    "max_file_size_mb": 50,
                    "max_total_size_mb": 200,
                }
            ),
            encoding="UTF-8",
        )

        real_dir = tmp_path / "real"
        real_dir.mkdir()
        symlink_dir = tmp_path / "link"
        symlink_dir.symlink_to(real_dir)

        with pytest.raises(SecurityError):
            cli.set_default_source(str(symlink_dir))


class TestSetDefaultDestination:
    """Tests for set_default_destination() function."""

    def test_set_default_destination_with_valid_directory(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """Test setting default destination with a valid directory."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        cli.set_default_destination(str(dest_dir))

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_destination"] == str(dest_dir.resolve())

    def test_set_default_destination_with_invalid_directory_raises_error(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_default_destination raises ConfigurationError for invalid directory."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text("{}")

        invalid_dir = tmp_path / "nonexistent"

        with pytest.raises(ConfigurationError, match="Invalid destination directory"):
            cli.set_default_destination(str(invalid_dir))

    def test_set_default_destination_allows_blank_to_clear(self, fake_home: Path) -> None:
        """Test that set_default_destination can clear the configured value with blank input."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "/some/source",
            "default_destination": "/some/destination",
            "auto_stage_enabled": True,
            "default_output_format": "html",
        }

        config_file.write_text(json.dumps(initial_config), encoding="UTF-8")

        cli.set_default_destination("")

        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_destination"] == ""
        assert config["default_source"] == initial_config["default_source"]
        assert config["auto_stage_enabled"] == initial_config["auto_stage_enabled"]
        assert config["default_output_format"] == initial_config["default_output_format"]

    def test_set_default_destination_with_symlink_raises_security_error(
        self, fake_home: Path, tmp_path: Path
    ) -> None:
        """set_default_destination raises SecurityError for symlink paths."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "default_source": "",
                    "default_destination": "",
                    "auto_stage_enabled": False,
                    "default_output_format": "markdown",
                    "default_convert_to": None,
                    "max_file_size_mb": 50,
                    "max_total_size_mb": 200,
                }
            ),
            encoding="UTF-8",
        )

        real_dir = tmp_path / "real"
        real_dir.mkdir()
        symlink_dir = tmp_path / "link"
        symlink_dir.symlink_to(real_dir)

        with pytest.raises(SecurityError):
            cli.set_default_destination(str(symlink_dir))


class TestSetAutoStage:
    """Tests for set_auto_stage() function."""

    def test_set_auto_stage_to_true(self, fake_home: Path) -> None:
        """Test setting auto_stage_enabled to True."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        cli.set_auto_stage(True)

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["auto_stage_enabled"] is True

    def test_set_auto_stage_to_false(self, fake_home: Path) -> None:
        """Test setting auto_stage_enabled to False."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": True,
            "default_output_format": "markdown",
        }

        with open(config_file, "w", encoding="UTF-8") as f:
            json.dump(initial_config, f)

        cli.set_auto_stage(False)

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["auto_stage_enabled"] is False


class TestSetDefaultOutputFormat:
    """Tests for set_default_output_format() function."""

    def test_set_default_output_format_markdown(self, fake_home: Path) -> None:
        """Test setting default output format to markdown."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "html"}')

        cli.set_default_output_format("markdown")

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_output_format"] == "markdown"

    def test_set_default_output_format_html(self, fake_home: Path) -> None:
        """Test setting default output format to html."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "markdown"}')

        cli.set_default_output_format("html")

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_output_format"] == "html"

    def test_set_default_output_format_text(self, fake_home: Path) -> None:
        """Test setting default output format to text."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "markdown"}')

        cli.set_default_output_format("text")

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_output_format"] == "text"

    def test_set_default_output_format_case_insensitive(self, fake_home: Path) -> None:
        """Test that set_default_output_format accepts case variations."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "html"}')

        cli.set_default_output_format("MARKDOWN")

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_output_format"] == "markdown"

    def test_set_default_output_format_mixed_case(self, fake_home: Path) -> None:
        """Test that set_default_output_format handles mixed case input."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "markdown"}')

        cli.set_default_output_format("Html")

        with open(config_file, "r", encoding="UTF-8") as f:
            config = json.load(f)

        assert config["default_output_format"] == "html"

    def test_set_default_output_format_invalid_raises_error(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_default_output_format raises ValidationError for invalid format."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text('{"default_output_format": "markdown"}')

        with pytest.raises(ValidationError) as exc_info:
            cli.set_default_output_format("invalid_format")

        assert "Invalid `--output-style`" in str(exc_info.value)
        assert "Use one of: markdown, html, text." in str(exc_info.value)


class TestSetDefaultConvertTo:
    """Tests for set_default_convert_to() function."""

    def test_set_default_convert_to_normalizes_value(self, fake_home: Path) -> None:
        """Test that set_default_convert_to normalizes input."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text(json.dumps({"default_convert_to": None}), encoding="UTF-8")

        cli.set_default_convert_to(".WEBP")

        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_convert_to"] == "webp"

        cli.set_default_convert_to("")

        config = json.loads(config_file.read_text(encoding="UTF-8"))
        assert config["default_convert_to"] is None

    def test_set_default_convert_to_invalid_raises_error(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that set_default_convert_to raises ValidationError for invalid formats."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"
        config_file.write_text(json.dumps({"default_convert_to": None}), encoding="UTF-8")

        with pytest.raises(ValidationError, match="Invalid `--convert-to`"):
            cli.set_default_convert_to("tiff")


class TestGetConfigInput:
    """Tests for get_config_input() function."""

    def test_get_config_input_returns_existing_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_config_input returns existing value from current_config."""
        current_config = {"test_field": "existing_value"}

        # Mock click.prompt to track if it was called with correct defaults
        prompt_calls: list[tuple[str, dict[str, Any]]] = []

        def mock_prompt(text: str, **kwargs: Any) -> str:
            prompt_calls.append((text, kwargs))
            return kwargs["default"]

        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_input("test_field", "Enter test field", current_config, "default")

        assert result == "existing_value"
        assert len(prompt_calls) == 1
        assert prompt_calls[0][1]["default"] == "existing_value"

    def test_get_config_input_uses_default_when_existing_is_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_config_input uses `default` when existing value is None."""
        current_config: dict[str, str | None] = {"test_field": None}

        prompt_calls: list[tuple[str, dict[str, Any]]] = []

        def mock_prompt(text: str, **kwargs: Any) -> str:
            prompt_calls.append((text, kwargs))
            return kwargs["default"]

        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_input("test_field", "Enter test field", current_config, "default")

        assert result == "default"
        assert len(prompt_calls) == 1
        assert prompt_calls[0][1]["default"] == "default"

    def test_get_config_input_accepts_new_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that get_config_input accepts new user input."""
        current_config: dict[str, str] = {}

        def mock_prompt(text: str, **kwargs: Any) -> str:
            return "new_value"

        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_input("test_field", "Enter test field", current_config, "default")

        assert result == "new_value"


class TestGetConfigBooleanInput:
    """Tests for get_config_boolean_input() function."""

    def test_get_config_boolean_input_with_true_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_config_boolean_input with True as default."""
        current_config: dict[str, bool] = {}

        confirm_calls: list[tuple[str, dict[str, Any]]] = []

        def mock_confirm(text: str, **kwargs: Any) -> bool:
            confirm_calls.append((text, kwargs))
            return kwargs["default"]

        monkeypatch.setattr("click.confirm", mock_confirm)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_boolean_input("test_field", "Enable test?", current_config, True)

        assert result is True
        assert len(confirm_calls) == 1
        assert confirm_calls[0][1]["default"] is True

    def test_get_config_boolean_input_with_false_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_config_boolean_input with False as default."""
        current_config: dict[str, bool] = {}

        def mock_confirm(text: str, **kwargs: Any) -> bool:
            return kwargs["default"]

        monkeypatch.setattr("click.confirm", mock_confirm)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_boolean_input("test_field", "Enable test?", current_config, False)

        assert result is False

    def test_get_config_boolean_input_uses_existing_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_config_boolean_input uses existing value from config."""
        current_config = {"test_field": True}

        def mock_confirm(text: str, **kwargs: Any) -> bool:
            return kwargs["default"]

        monkeypatch.setattr("click.confirm", mock_confirm)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_config_boolean_input("test_field", "Enable test?", current_config, False)

        assert result is True


class TestGetValidatedDirectoryInput:
    """Tests for get_validated_directory_input() function."""

    def test_get_validated_directory_input_accepts_valid_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_directory_input accepts a valid directory path."""
        valid_dir = tmp_path / "valid"
        valid_dir.mkdir()

        current_config: dict[str, str] = {}

        def mock_get_config_input(
            field: str, message: str, current_config: dict[str, Any], default: str
        ) -> str:
            return str(valid_dir)

        monkeypatch.setattr(cli, "get_config_input", mock_get_config_input)
        monkeypatch.setattr("click.echo", lambda msg=None, **kwargs: None)
        monkeypatch.setattr("click.secho", lambda msg=None, **kwargs: None)

        result = cli.get_validated_directory_input(
            "test_field", "Enter directory", current_config, ""
        )

        assert result == str(valid_dir.resolve())

    def test_get_validated_directory_input_rejects_invalid_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_directory_input rejects invalid path and re-prompts."""
        valid_dir = tmp_path / "valid"
        valid_dir.mkdir()
        invalid_dir = tmp_path / "invalid"

        call_count = [0]

        def mock_get_config_input(
            field: str, message: str, current_config: dict[str, Any], default: str
        ) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                return str(invalid_dir)  # First call returns invalid
            return str(valid_dir)  # Second call returns valid

        error_messages: list[str] = []
        monkeypatch.setattr(cli, "get_config_input", mock_get_config_input)
        monkeypatch.setattr(
            "click.echo",
            lambda msg=None, **kwargs: error_messages.append(msg)
            if msg and kwargs.get("err")
            else None,
        )
        monkeypatch.setattr(
            "click.secho",
            lambda msg=None, **kwargs: error_messages.append(msg)
            if msg and kwargs.get("err")
            else None,
        )

        result = cli.get_validated_directory_input("test_field", "Enter directory", {}, "")

        assert result == str(valid_dir.resolve())
        assert call_count[0] == 2
        assert any("Invalid" in str(msg) for msg in error_messages)

    def test_get_validated_directory_input_accepts_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_directory_input accepts empty string and returns default."""

        def mock_get_config_input(
            field: str, message: str, current_config: dict[str, Any], default: str
        ) -> str:
            return "   "  # Whitespace only

        monkeypatch.setattr(cli, "get_config_input", mock_get_config_input)
        monkeypatch.setattr("click.echo", lambda msg=None, **kwargs: None)
        monkeypatch.setattr("click.secho", lambda msg=None, **kwargs: None)

        result = cli.get_validated_directory_input(
            "test_field", "Enter directory", {}, "default_value"
        )

        assert result == "default_value"


class TestGetValidatedInput:
    """Tests for get_validated_input() function."""

    def test_get_validated_input_validates_against_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_input validates against options list."""
        current_config: dict[str, str] = {}

        def mock_prompt(text: str, **kwargs: Any) -> str:
            return "html"

        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_validated_input(
            "format", "Enter format", current_config, "markdown", options=["markdown", "html"]
        )

        assert result == "html"

    def test_get_validated_input_rejects_invalid_option(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_input rejects invalid option and re-prompts."""
        current_config: dict[str, str] = {}
        call_count = [0]

        def mock_prompt(text: str, **kwargs: Any) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                return "invalid"
            return "markdown"

        error_messages: list[str] = []
        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)
        monkeypatch.setattr("click.echo", lambda msg, **kwargs: error_messages.append(msg))
        monkeypatch.setattr("click.secho", lambda msg, **kwargs: error_messages.append(msg))

        result = cli.get_validated_input(
            "format", "Enter format", current_config, "html", options=["markdown", "html"]
        )

        assert result == "markdown"
        assert call_count[0] == 2
        assert any("Invalid value" in str(msg) for msg in error_messages)

    def test_get_validated_input_case_insensitive_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_validated_input performs case-insensitive validation."""
        current_config: dict[str, str] = {}

        def mock_prompt(text: str, **kwargs: Any) -> str:
            return "MARKDOWN"

        monkeypatch.setattr("click.prompt", mock_prompt)
        monkeypatch.setattr("click.style", lambda text, **kwargs: text)

        result = cli.get_validated_input(
            "format", "Enter format", current_config, "html", options=["markdown", "html"]
        )

        assert result == "MARKDOWN"


class TestAtomicWriteJson:
    """Tests for atomic_write_json() function."""

    def test_atomic_write_json_creates_file(self, tmp_path: Path) -> None:
        """Test that atomic_write_json creates a new file."""
        config_file = tmp_path / "config.json"
        test_data = {"key": "value", "number": 42}

        cli.atomic_write_json(config_file, test_data, mode=0o600)

        assert config_file.exists()
        with open(config_file, "r", encoding="UTF-8") as f:
            result = json.load(f)
        assert result == test_data

    def test_atomic_write_json_sets_permissions(self, tmp_path: Path) -> None:
        """Test that atomic_write_json sets file permissions correctly."""
        config_file = tmp_path / "config.json"
        test_data = {"key": "value"}

        cli.atomic_write_json(config_file, test_data, mode=0o600)

        # Check file permissions
        assert (config_file.stat().st_mode & 0o777) == 0o600

    def test_atomic_write_json_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that atomic_write_json overwrites an existing file atomically."""
        config_file = tmp_path / "config.json"

        # Write initial data
        initial_data = {"old_key": "old_value"}
        cli.atomic_write_json(config_file, initial_data, mode=0o600)

        # Overwrite with new data
        new_data = {"new_key": "new_value", "another": 123}
        cli.atomic_write_json(config_file, new_data, mode=0o600)

        # Verify new data is written
        with open(config_file, "r", encoding="UTF-8") as f:
            result = json.load(f)
        assert result == new_data
        assert "old_key" not in result

    def test_atomic_write_json_crash_simulation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that crashes during write don't corrupt file."""
        config_file = tmp_path / "config.json"

        # Write initial config
        initial_config = {"key": "value1"}
        cli.atomic_write_json(config_file, initial_config, mode=0o600)

        # Simulate crash during write by mocking os.replace
        call_count = [0]
        original_replace = cli.os.replace

        def crashing_replace(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("Simulated crash")
            return original_replace(*args)

        monkeypatch.setattr(cli.os, "replace", crashing_replace)

        # Attempt write that will crash
        with pytest.raises(OSError, match="Simulated crash"):
            cli.atomic_write_json(config_file, {"key": "value2"}, mode=0o600)

        # Verify original file still intact and valid
        with open(config_file, "r", encoding="UTF-8") as f:
            recovered_config = json.load(f)

        assert recovered_config == initial_config  # Not corrupted!

    def test_atomic_write_json_cleanup_on_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that temp files are cleaned up on failure."""
        config_file = tmp_path / "config.json"

        # Mock json.dump to fail
        def failing_dump(*args, **kwargs):
            raise ValueError("Simulated write failure")

        monkeypatch.setattr(json, "dump", failing_dump)

        # Attempt write that will fail
        with pytest.raises(ValueError, match="Simulated write failure"):
            cli.atomic_write_json(config_file, {"key": "value"}, mode=0o600)

        # Verify no temp files left in directory
        temp_files = list(tmp_path.glob(".config.json_*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_json_preserves_json_format(self, tmp_path: Path) -> None:
        """Test that atomic_write_json writes properly formatted JSON."""
        config_file = tmp_path / "config.json"
        test_data = {
            "default_source": "/path/to/source",
            "default_destination": "/path/to/dest",
            "auto_stage_enabled": True,
            "default_output_format": "markdown",
        }

        cli.atomic_write_json(config_file, test_data, mode=0o600)

        # Read raw file content to verify formatting
        with open(config_file, "r", encoding="UTF-8") as f:
            content = f.read()

        # Verify it's valid JSON with proper indentation
        assert content.count("\n") > 4  # Multi-line JSON
        assert "    " in content  # Indented (4 spaces)

        # Verify it can be parsed back
        parsed = json.loads(content)
        assert parsed == test_data

    def test_atomic_write_json_calls_fsync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that atomic_write_json fsyncs file and directory for durability."""
        fsync_targets = []
        original_fsync = os.fsync

        def mock_fsync(fd: int) -> None:
            fsync_targets.append(os.fstat(fd).st_mode)
            return original_fsync(fd)

        monkeypatch.setattr(os, "fsync", mock_fsync)

        config_file = tmp_path / "config.json"
        cli.atomic_write_json(config_file, {"key": "value"})

        assert len(fsync_targets) == 2, "fsync must be called for file and directory"
        assert any(stat.S_ISREG(mode) for mode in fsync_targets)
        assert any(stat.S_ISDIR(mode) for mode in fsync_targets)


class TestConfigPermissionEnforcement:
    """Tests for secure config writing."""

    def test_config_permissions_enforced_on_update(self, fake_home: Path, tmp_path: Path) -> None:
        """Ensure config permissions reset to 0o600 on update."""
        config_path = fake_home / ".config" / "wslshot" / "config.json"
        initial_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
        }
        config_path.write_text(json.dumps(initial_config), encoding="UTF-8")
        config_path.chmod(0o644)

        new_source = tmp_path / "source"
        new_source.mkdir()

        cli.set_default_source(str(new_source))

        assert (config_path.stat().st_mode & 0o777) == 0o600
        with open(config_path, "r", encoding="UTF-8") as f:
            config = json.load(f)
        assert config["default_source"] == str(new_source.resolve())

    def test_config_update_warns_on_insecure_permissions(
        self, fake_home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Ensure warning is emitted when permissions are fixed."""
        config_path = fake_home / ".config" / "wslshot" / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "default_source": "",
                    "default_destination": "",
                    "auto_stage_enabled": False,
                    "default_output_format": "markdown",
                }
            ),
            encoding="UTF-8",
        )
        config_path.chmod(0o666)

        new_source = tmp_path / "source"
        new_source.mkdir()

        cli.set_default_source(str(new_source))

        captured = capsys.readouterr()
        assert "Config file permissions were too open (0o666)" in captured.err

    def test_config_write_rejects_symlinks(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reject writing config when path is a symlink."""
        config_path = fake_home / ".config" / "wslshot" / "config.json"
        target = tmp_path / "real_config.json"
        target.write_text("{}", encoding="UTF-8")
        if config_path.exists():
            config_path.unlink()
        config_path.symlink_to(target)

        new_source = tmp_path

        exit_codes: list[int] = []

        def mock_exit(code: int) -> None:
            exit_codes.append(code)
            raise SystemExit(code)

        error_messages: list[str] = []
        monkeypatch.setattr(sys, "exit", mock_exit)
        monkeypatch.setattr(
            "click.echo",
            lambda msg=None, **kwargs: error_messages.append(msg)
            if msg and kwargs.get("err")
            else None,
        )

        with pytest.raises(SystemExit):
            cli.set_default_source(str(new_source))

        assert exit_codes == [1]
        assert any("Config file is a symlink" in str(msg) for msg in error_messages)

    def test_config_write_rejects_broken_symlinks(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reject writing config when path is a broken symlink."""
        config_path = fake_home / ".config" / "wslshot" / "config.json"
        target = tmp_path / "missing.json"
        if config_path.exists():
            config_path.unlink()
        config_path.symlink_to(target)

        new_source = tmp_path

        exit_codes: list[int] = []

        def mock_exit(code: int) -> None:
            exit_codes.append(code)
            raise SystemExit(code)

        error_messages: list[str] = []
        monkeypatch.setattr(sys, "exit", mock_exit)
        monkeypatch.setattr(
            "click.echo",
            lambda msg=None, **kwargs: error_messages.append(msg)
            if msg and kwargs.get("err")
            else None,
        )

        with pytest.raises(SystemExit):
            cli.set_default_source(str(new_source))

        assert exit_codes == [1]
        assert any("Config file is a symlink" in str(msg) for msg in error_messages)

    def test_get_config_path_or_exit_rejects_symlink(
        self, fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ensure helper exits cleanly when config path is a symlink."""
        config_path = fake_home / ".config" / "wslshot" / "config.json"
        target = tmp_path / "real_config.json"
        target.write_text("{}", encoding="UTF-8")
        if config_path.exists():
            config_path.unlink()
        config_path.symlink_to(target)

        exit_codes: list[int] = []

        def mock_exit(code: int) -> None:
            exit_codes.append(code)
            raise SystemExit(code)

        error_messages: list[str] = []
        monkeypatch.setattr(sys, "exit", mock_exit)
        monkeypatch.setattr(
            "click.echo",
            lambda msg=None, **kwargs: error_messages.append(msg)
            if msg and kwargs.get("err")
            else None,
        )

        with pytest.raises(SystemExit):
            cli.get_config_file_path_or_exit()

        assert exit_codes == [1]
        assert any("Config file is a symlink" in str(msg) for msg in error_messages)

    def test_chmod_failure_still_writes_with_correct_permissions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When chmod fails on existing file, atomic write still succeeds with 0o600."""
        config_path = tmp_path / "config.json"
        config_path.write_text('{"old": "data"}', encoding="UTF-8")
        config_path.chmod(0o644)

        # Mock Path.chmod to fail
        original_chmod = Path.chmod

        def failing_chmod(self: Path, mode: int) -> None:
            if self == config_path:
                raise OSError("Permission denied")
            return original_chmod(self, mode)

        monkeypatch.setattr(Path, "chmod", failing_chmod)

        new_config = {"new": "data", "updated": True}
        cli.write_config_safely(config_path, new_config)

        # Verify config was written correctly
        with open(config_path, "r", encoding="UTF-8") as f:
            written_config = json.load(f)
        assert written_config == new_config

        # Verify final permissions are 0o600 (from atomic write's temp file)
        assert (config_path.stat().st_mode & 0o777) == 0o600

        # Verify warning was emitted
        captured = capsys.readouterr()
        assert "Could not fix permissions" in captured.err
        assert "atomic write will replace" in captured.err


class TestBestEffortDurability:
    """Tests for best-effort directory fsync behavior."""

    def test_directory_fsync_failure_warns_but_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When directory fsync fails, function warns but returns successfully."""
        config_path = tmp_path / "config.json"
        test_data = {"key": "value"}

        fsync_call_count = [0]
        original_fsync = os.fsync

        def selective_failing_fsync(fd: int) -> None:
            fsync_call_count[0] += 1
            # atomic_write_json() calls fsync twice: first on the file, then on the directory.
            # Fail only on directory fsync (second call).
            if fsync_call_count[0] == 2:
                raise OSError("Simulated directory fsync failure")
            return original_fsync(fd)

        monkeypatch.setattr(os, "fsync", selective_failing_fsync)

        # Should not raise
        cli.atomic_write_json(config_path, test_data)

        # Verify data was written
        with open(config_path, "r", encoding="UTF-8") as f:
            written_data = json.load(f)
        assert written_data == test_data

        # Verify warning was emitted
        captured = capsys.readouterr()
        assert "durability not guaranteed" in captured.err

    def test_directory_fsync_failure_does_not_corrupt_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When directory fsync fails, file content remains valid."""
        config_path = tmp_path / "config.json"

        # Write initial config
        initial_data = {"initial": "data"}
        cli.atomic_write_json(config_path, initial_data)

        fsync_call_count = [0]
        original_fsync = os.fsync

        def selective_failing_fsync(fd: int) -> None:
            fsync_call_count[0] += 1
            # atomic_write_json() calls fsync twice: first on the file, then on the directory.
            # Fail only on directory fsync (second call).
            if fsync_call_count[0] == 2:
                raise OSError("Simulated directory fsync failure")
            return original_fsync(fd)

        monkeypatch.setattr(os, "fsync", selective_failing_fsync)

        # Update with new data
        new_data = {"new": "data", "updated": True}
        cli.atomic_write_json(config_path, new_data)

        # Verify new data was written (not corrupted, not old data)
        with open(config_path, "r", encoding="UTF-8") as f:
            written_data = json.load(f)
        assert written_data == new_data
        assert "initial" not in written_data


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validate_config_with_valid_config(self, tmp_path: Path) -> None:
        """Test that valid config passes validation and is normalized."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        raw_config = {
            "default_source": str(source_dir),
            "default_destination": str(dest_dir),
            "auto_stage_enabled": True,
            "default_output_format": "HTML",  # Mixed case
            "default_convert_to": ".PNG",  # With dot
            "max_file_size_mb": 25,
            "max_total_size_mb": 100,
        }

        result = cli.validate_config(raw_config)

        # Paths are resolved to absolute paths
        assert result["default_source"] == str(source_dir.resolve())
        assert result["default_destination"] == str(dest_dir.resolve())
        assert result["auto_stage_enabled"] is True
        # Values are normalized
        assert result["default_output_format"] == "html"
        assert result["default_convert_to"] == "png"
        assert result["max_file_size_mb"] == 25
        assert result["max_total_size_mb"] == 100

    def test_validate_config_fills_missing_with_defaults(self) -> None:
        """Test that missing keys are filled with defaults."""
        raw_config: dict[str, object] = {}

        result = cli.validate_config(raw_config)

        assert result["default_source"] == ""
        assert result["default_destination"] == ""
        assert result["auto_stage_enabled"] is False
        assert result["default_output_format"] == "markdown"
        assert result["default_convert_to"] is None
        assert result["max_file_size_mb"] == 50
        assert result["max_total_size_mb"] == 200

    def test_validate_config_warns_unknown_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that unknown keys trigger a warning."""
        raw_config = {
            "unknwon_key": "value",  # Typo
            "another_unknown": 123,
        }

        cli.validate_config(raw_config)

        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "Unknown config keys ignored" in captured.err
        assert "another_unknown" in captured.err
        assert "unknwon_key" in captured.err

    def test_validate_config_raises_on_invalid_type(self) -> None:
        """Test that wrong type raises ConfigurationError."""
        raw_config = {
            "auto_stage_enabled": "not_a_bool",  # Invalid: wrong type
        }

        with pytest.raises(ConfigurationError, match="Invalid value for 'auto_stage_enabled'"):
            cli.validate_config(raw_config)

    def test_validate_config_raises_on_invalid_value(self) -> None:
        """Test that invalid value raises ConfigurationError."""
        raw_config = {
            "default_output_format": "invalid_format",
        }

        with pytest.raises(ConfigurationError, match="Invalid value for 'default_output_format'"):
            cli.validate_config(raw_config)

    def test_validate_config_allows_nonexistent_paths_with_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that non-existent directory paths are allowed with a warning."""
        nonexistent_source = tmp_path / "does_not_exist_source"
        nonexistent_dest = tmp_path / "does_not_exist_dest"

        raw_config = {
            "default_source": str(nonexistent_source),
            "default_destination": str(nonexistent_dest),
        }

        result = cli.validate_config(raw_config)

        # Paths are preserved as-is (not rejected)
        assert result["default_source"] == str(nonexistent_source)
        assert result["default_destination"] == str(nonexistent_dest)

        # Warnings were issued
        captured = capsys.readouterr()
        assert "Warning:" in captured.err
        assert "default source does not exist" in captured.err
        assert "default destination does not exist" in captured.err

    def test_validate_config_empty_path_uses_default(self) -> None:
        """Test that empty path strings use default (empty string)."""
        raw_config = {
            "default_source": "",
            "default_destination": "   ",  # Whitespace only
        }

        result = cli.validate_config(raw_config)

        assert result["default_source"] == ""
        assert result["default_destination"] == ""

    def test_read_config_validates_and_autofix(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid config is auto-fixed by recreating with defaults."""
        config_file = fake_home / ".config" / "wslshot" / "config.json"

        # Write config with invalid value
        invalid_config = {
            "default_output_format": 12345,  # Wrong type: int instead of str
        }
        config_file.write_text(json.dumps(invalid_config), encoding="UTF-8")

        # Non-interactive mode: should reset to defaults
        monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)

        result = cli.read_config(config_file)

        # Should return defaults after auto-fix
        assert result == cli.DEFAULT_CONFIG

        # Config file should be reset to defaults
        with open(config_file, "r", encoding="UTF-8") as f:
            written_config = json.load(f)
        assert written_config == cli.DEFAULT_CONFIG

        # Original should be backed up
        backup_file = config_file.with_name(f"{config_file.name}.corrupted")
        assert backup_file.exists()
        with open(backup_file, "r", encoding="UTF-8") as f:
            backup_config = json.load(f)
        assert backup_config == invalid_config
