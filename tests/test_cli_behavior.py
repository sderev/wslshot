from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import CliRunner
from conftest import create_test_image

from wslshot import cli


def test_generate_screenshot_name_uses_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    image_path = Path("/tmp/source/screenshot.png")
    assert cli.generate_screenshot_name(image_path) == f"{fake_uuid.hex}.png"


def test_generate_screenshot_name_for_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_uuid = UUID("87654321-4321-6789-4321-678987654321")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    gif_path = Path("/tmp/source/animation.gif")
    assert cli.generate_screenshot_name(gif_path) == f"{fake_uuid.hex}.gif"


def test_format_screenshots_path_for_git_skips_external_paths(tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    git_root.mkdir()

    inside = git_root / "assets" / "images" / "shot.png"
    inside.parent.mkdir(parents=True)
    create_test_image(inside)

    outside = tmp_path / "other" / "shot.png"
    outside.parent.mkdir()
    create_test_image(outside)

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
    create_test_image(screenshot)

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


# Edge case tests added below


def test_generate_screenshot_name_uppercase_jpg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that uppercase .JPG extension is normalized to lowercase."""
    fake_uuid = UUID("abcdefab-1234-5678-abcd-1234567890ab")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    image_path = Path("/tmp/source/Screenshot.JPG")
    result = cli.generate_screenshot_name(image_path)

    assert result == f"{fake_uuid.hex}.jpg"
    assert result.endswith(".jpg")  # Verify lowercase


def test_generate_screenshot_name_uppercase_jpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that uppercase .JPEG extension is normalized to lowercase."""
    fake_uuid = UUID("bbbbbbbb-2222-3333-4444-555555555555")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    image_path = Path("/tmp/source/Photo.JPEG")
    result = cli.generate_screenshot_name(image_path)

    assert result == f"{fake_uuid.hex}.jpeg"
    assert result.endswith(".jpeg")


def test_generate_screenshot_name_mixed_case_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that mixed case .PnG extension is normalized to lowercase."""
    fake_uuid = UUID("cccccccc-3333-4444-5555-666666666666")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    image_path = Path("/tmp/source/Image.PnG")
    result = cli.generate_screenshot_name(image_path)

    assert result == f"{fake_uuid.hex}.png"
    assert result.endswith(".png")


def test_stage_screenshots_handles_git_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that staging continues gracefully when git add fails."""
    from subprocess import CalledProcessError

    git_root = tmp_path / "repo"
    git_root.mkdir()

    error_msgs: list[str] = []

    def failing_run(cmd, **kwargs):
        raise CalledProcessError(1, cmd)

    def capture_echo(msg, **kwargs):
        error_msgs.append(str(msg))

    monkeypatch.setattr(cli.subprocess, "run", failing_run)
    monkeypatch.setattr(cli.click, "echo", capture_echo)

    # Should not raise exception
    cli.stage_screenshots((Path("shot.png"),), git_root)

    assert any("Auto-staging failed" in msg for msg in error_msgs)


def test_format_screenshots_path_for_git_empty_tuple(tmp_path: Path) -> None:
    """Test that empty tuple input returns empty tuple output."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    result = cli.format_screenshots_path_for_git((), git_root)

    assert result == ()


def test_format_screenshots_path_for_git_all_outside_repo(tmp_path: Path) -> None:
    """Test that all paths outside repo returns empty tuple."""
    git_root = tmp_path / "repo"
    git_root.mkdir()

    outside1 = tmp_path / "other1" / "shot1.png"
    outside1.parent.mkdir()
    create_test_image(outside1)

    outside2 = tmp_path / "other2" / "shot2.png"
    outside2.parent.mkdir()
    create_test_image(outside2)

    result = cli.format_screenshots_path_for_git((outside1, outside2), git_root)

    assert result == ()


def test_copy_screenshots_empty_tuple(tmp_path: Path) -> None:
    """Test that copy_screenshots with empty tuple returns empty tuple."""
    destination = tmp_path / "dest"
    destination.mkdir()

    result = cli.copy_screenshots((), destination)

    assert result == ()
