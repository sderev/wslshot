from __future__ import annotations

import json
from pathlib import Path

import pytest

from wslshot import cli


def test_get_destination_returns_git_when_in_repo(fake_home, tmp_path, monkeypatch):
    """Test returns git image destination when in git repo."""
    # Setup config with default_destination
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

    # Mock git functions
    git_dest = tmp_path / "repo" / "assets" / "images"
    git_dest.mkdir(parents=True)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_repo_img_destination", lambda: git_dest)

    result = cli.get_destination()
    assert result == git_dest


def test_get_destination_prefers_git_over_config(fake_home, tmp_path, monkeypatch):
    """Test git destination takes priority over config default_destination."""
    # Setup config with default_destination
    config_dest = tmp_path / "from_config"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Mock git functions
    git_dest = tmp_path / "repo" / "assets" / "images"
    git_dest.mkdir(parents=True)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_repo_img_destination", lambda: git_dest)

    result = cli.get_destination()
    assert result == git_dest  # Git wins over config


def test_get_destination_calls_git_repo_img_destination_when_in_repo(
    fake_home, tmp_path, monkeypatch
):
    """Test calls get_git_repo_img_destination() when in git repo."""
    # Setup config
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

    # Track function calls
    git_img_dest_called = False

    def mock_get_git_repo_img_destination():
        nonlocal git_img_dest_called
        git_img_dest_called = True
        git_dest = tmp_path / "repo" / "assets" / "images"
        git_dest.mkdir(parents=True)
        return git_dest

    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_repo_img_destination", mock_get_git_repo_img_destination)

    cli.get_destination()
    assert git_img_dest_called


def test_get_destination_returns_config_default_when_not_in_git_repo(
    fake_home, tmp_path, monkeypatch
):
    """Test returns config default_destination when NOT in git repo."""
    # Setup config with default_destination
    config_dest = tmp_path / "from_config"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = cli.get_destination()
    assert result == config_dest


def test_get_destination_reads_config_from_correct_location(fake_home, monkeypatch):
    """Test reads config from correct location using fake_home."""
    # Setup config with specific default_destination
    config_dest = fake_home / "my_screenshots"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = cli.get_destination()
    assert result == config_dest
    # Verify the config was read from the correct location
    assert config_file.exists()


def test_get_destination_config_default_takes_priority_over_cwd(
    fake_home, tmp_path, monkeypatch
):
    """Test config default_destination takes priority over cwd."""
    # Setup config with default_destination
    config_dest = tmp_path / "from_config"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Set a different cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = cli.get_destination()
    assert result == config_dest  # Config wins over cwd
    assert result != Path.cwd()


def test_get_destination_returns_cwd_when_not_in_git_and_no_config_default(
    fake_home, tmp_path, monkeypatch
):
    """Test returns Path.cwd() when NOT in git repo AND no config default."""
    # Setup config with empty default_destination
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

    # Set cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = cli.get_destination()
    assert result == Path.cwd()
    assert result == cwd_dir


def test_get_destination_returns_cwd_when_config_default_is_empty_string(
    fake_home, tmp_path, monkeypatch
):
    """Test returns cwd when config default_destination is empty string."""
    # Setup config with empty string default_destination
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

    # Set cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    result = cli.get_destination()
    assert result == Path.cwd()
    assert result == cwd_dir


def test_get_destination_priority_cascade_git_wins_over_config(
    fake_home, tmp_path, monkeypatch
):
    """Test complete priority cascade: git wins over config."""
    # Setup config with default_destination
    config_dest = tmp_path / "from_config"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Mock git functions to return True and a specific destination
    git_dest = tmp_path / "repo" / "assets" / "images"
    git_dest.mkdir(parents=True)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_repo_img_destination", lambda: git_dest)

    # Set a different cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    result = cli.get_destination()
    # Git wins over both config and cwd
    assert result == git_dest
    assert result != config_dest
    assert result != Path.cwd()


def test_get_destination_priority_cascade_config_wins_over_cwd(
    fake_home, tmp_path, monkeypatch
):
    """Test config default_destination wins over cwd when git=False."""
    # Setup config with default_destination
    config_dest = tmp_path / "from_config"
    config_dest.mkdir()
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "default_source": "",
                "default_destination": str(config_dest),
                "auto_stage_enabled": False,
                "default_output_format": "markdown",
            }
        )
    )

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    # Set a different cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    result = cli.get_destination()
    # Config wins over cwd
    assert result == config_dest
    assert result != Path.cwd()


def test_get_destination_cwd_is_last_resort(fake_home, tmp_path, monkeypatch):
    """Test cwd is last resort when no git and no config default."""
    # Setup config with empty default_destination
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

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    # Set cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    result = cli.get_destination()
    # cwd is the last resort
    assert result == Path.cwd()
    assert result == cwd_dir


def test_get_destination_with_missing_config_file(fake_home, tmp_path, monkeypatch):
    """Test handles missing config file by creating default."""
    # Setup config directory but no file
    config_dir = fake_home / ".config" / "wslshot"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Create a default config that will be returned when config is missing
    default_config = {
        "default_source": "",
        "default_destination": "",
        "auto_stage_enabled": False,
        "default_output_format": "markdown",
    }

    # Mock read_config to return default config when file is missing
    def mock_read_config(path):
        if not config_file.exists():
            # Simulate what happens when config is created
            config_file.write_text(json.dumps(default_config))
        with open(config_file, "r") as f:
            return json.load(f)

    monkeypatch.setattr(cli, "read_config", mock_read_config)
    monkeypatch.setattr(cli, "get_config_file_path", lambda: config_file)

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    # Set cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    # This should return cwd when config has empty default_destination
    result = cli.get_destination()
    assert result == Path.cwd()
    # Verify config file was created
    assert config_file.exists()


def test_get_destination_with_malformed_config_file(fake_home, tmp_path, monkeypatch):
    """Test handles malformed config file gracefully."""
    # Create malformed JSON config
    config_file = fake_home / ".config" / "wslshot" / "config.json"
    config_file.write_text("{invalid json")

    # Default config that should be used after handling malformed JSON
    default_config = {
        "default_source": "",
        "default_destination": "",
        "auto_stage_enabled": False,
        "default_output_format": "markdown",
    }

    # Mock read_config to simulate handling JSONDecodeError
    def mock_read_config(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Simulate write_config behavior: recreate valid config
            path.write_text(json.dumps(default_config))
            return default_config

    monkeypatch.setattr(cli, "read_config", mock_read_config)
    monkeypatch.setattr(cli, "get_config_file_path", lambda: config_file)

    # Mock git to return False
    monkeypatch.setattr(cli, "is_git_repo", lambda: False)

    # Set cwd
    cwd_dir = tmp_path / "current_dir"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)

    # This should handle the JSONDecodeError and return cwd
    result = cli.get_destination()
    assert result == Path.cwd()
    # Verify config file was rewritten with valid JSON
    assert config_file.exists()
    with open(config_file) as f:
        config = json.load(f)  # Should not raise JSONDecodeError
        assert "default_destination" in config
