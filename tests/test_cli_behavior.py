from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import CliRunner
from wslshot import cli


def test_generate_screenshot_name_uses_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    image_path = Path("/tmp/source/screenshot.png")
    assert cli.generate_screenshot_name(image_path) == f"screenshot_{fake_uuid.hex}.png"


def test_generate_screenshot_name_for_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_uuid = UUID("87654321-4321-6789-4321-678987654321")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    gif_path = Path("/tmp/source/animation.gif")
    assert cli.generate_screenshot_name(gif_path) == f"animated_{fake_uuid.hex}.gif"


def test_format_screenshots_path_for_git_skips_external_paths(tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    git_root.mkdir()

    inside = git_root / "assets" / "images" / "shot.png"
    inside.parent.mkdir(parents=True)
    inside.touch()

    outside = tmp_path / "other" / "shot.png"
    outside.parent.mkdir()
    outside.touch()

    result = cli.format_screenshots_path_for_git(
        (inside, outside),
        git_root,
    )

    assert list(result) == [inside.relative_to(git_root)]


def test_stage_screenshots_uses_repo_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    git_root.mkdir()

    received: list[Path] = []

    def fake_run(cmd, check, cwd):
        received.append(Path(cwd))
        assert cmd[:2] == ["git", "add"]
        return None

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.stage_screenshots((Path("assets/images/shot.png"),), git_root)

    assert received == [git_root]


def test_fetch_skips_staging_when_destination_outside_repo(
    tmp_path: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "outside"
    repo_root = tmp_path / "repo"

    source.mkdir()
    destination.mkdir()
    repo_root.mkdir()

    screenshot = source / "screen.png"
    screenshot.write_bytes(b"fake")

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

    stage_called = []

    def fake_stage(screenshots, git_root):
        stage_called.append((screenshots, git_root))

    printed_args = {}

    def fake_print(output_format, screenshots, *, relative_to_repo):
        printed_args["output_format"] = output_format
        printed_args["screenshots"] = screenshots
        printed_args["relative_to_repo"] = relative_to_repo

    monkeypatch.setattr(cli, "stage_screenshots", fake_stage)
    monkeypatch.setattr(cli, "print_formatted_path", fake_print)
    monkeypatch.setattr(cli, "is_git_repo", lambda: True)
    monkeypatch.setattr(cli, "get_git_root", lambda: repo_root)

    runner = CliRunner()
    result = runner.invoke(
        cli.wslshot,
        [
            "fetch",
            "--source",
            str(source),
            "--destination",
            str(destination),
        ],
        env={"HOME": str(fake_home)},
    )

    assert result.exit_code == 0
    assert stage_called == []
    assert printed_args["relative_to_repo"] is False
    printed_path = printed_args["screenshots"][0]
    assert Path(printed_path).is_absolute()


def test_fetch_rejects_non_positive_count(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.wslshot, ["fetch", "--count", "0"])

    assert result.exit_code != 0
    assert "Invalid value for '--count'" in result.output
