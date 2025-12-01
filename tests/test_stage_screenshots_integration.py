from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import create_git_repo, create_test_image, get_staged_files, is_file_staged
from wslshot import cli


def test_stage_single_screenshot_with_real_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = repo / "screenshot.png"
    create_test_image(screenshot)

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    assert get_staged_files(repo) == ["screenshot.png"]
    assert is_file_staged(repo, screenshot)


def test_stage_multiple_screenshots_batch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshots = []
    for index in range(3):
        file_path = repo / f"screenshot_{index}.png"
        create_test_image(file_path)
        screenshots.append(file_path)

    cli.stage_screenshots(tuple(path.relative_to(repo) for path in screenshots), repo)

    staged_files = set(get_staged_files(repo))
    assert staged_files == {f"screenshot_{i}.png" for i in range(3)}


def test_stage_screenshots_in_subdirectory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    subdir = repo / "screenshots"
    subdir.mkdir()

    nested_files = (
        create_test_image(subdir / "nested1.png"),
        create_test_image(subdir / "nested2.png"),
    )

    cli.stage_screenshots(tuple(path.relative_to(repo) for path in nested_files), repo)

    staged_files = set(get_staged_files(repo))
    assert staged_files == {f"screenshots/{path.name}" for path in nested_files}


# ====================  Edge Case and Fallback Tests ====================


def test_stage_empty_screenshot_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    cli.stage_screenshots((), repo)

    assert get_staged_files(repo) == []


def test_stage_nonexistent_file(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    nonexistent = repo / "nonexistent.png"

    cli.stage_screenshots((nonexistent.relative_to(repo),), repo)

    captured = capsys.readouterr()
    assert "Warning" in captured.err or "Failed" in captured.err
    assert get_staged_files(repo) == []


def test_stage_file_outside_repo(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_file = create_test_image(external_dir / "external.png")

    cli.stage_screenshots((external_file,), repo)

    captured = capsys.readouterr()
    assert "Warning" in captured.err or "Failed" in captured.err
    assert get_staged_files(repo) == []
    assert is_file_staged(repo, external_file) is False


def test_stage_screenshots_with_spaces_in_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = create_test_image(repo / "screen shot 1.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    assert is_file_staged(repo, screenshot)


def test_stage_screenshots_with_unicode_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = create_test_image(repo / "screenshot_日本語.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    assert is_file_staged(repo, screenshot)


def test_stage_partial_failure(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    valid1 = create_test_image(repo / "valid1.png")
    valid2 = create_test_image(repo / "valid2.png")
    invalid = Path("nonexistent.png")

    cli.stage_screenshots(
        (valid1.relative_to(repo), valid2.relative_to(repo), invalid), repo
    )

    staged_files = set(get_staged_files(repo))
    assert "valid1.png" in staged_files
    assert "valid2.png" in staged_files

    captured = capsys.readouterr()
    assert "Warning" in captured.err or "Failed" in captured.err


# ====================  Git State and Performance Tests ====================


def test_stage_already_staged_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = create_test_image(repo / "screenshot.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)
    assert is_file_staged(repo, screenshot)

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)
    assert is_file_staged(repo, screenshot)


def test_stage_modified_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = create_test_image(repo / "screenshot.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True)

    screenshot.write_bytes(b"modified content")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    assert is_file_staged(repo, screenshot)


def test_stage_file_in_dirty_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    unrelated = repo / "unrelated.txt"
    unrelated.write_text("unrelated content")

    screenshot = create_test_image(repo / "screenshot.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    staged_files = set(get_staged_files(repo))
    assert "screenshot.png" in staged_files
    assert "unrelated.txt" not in staged_files


def test_stage_does_not_auto_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshot = create_test_image(repo / "screenshot.png")

    cli.stage_screenshots((screenshot.relative_to(repo),), repo)

    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout.strip() == ""


def test_stage_many_files_performance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    create_git_repo(repo)

    screenshots = []
    for i in range(50):
        screenshot = create_test_image(repo / f"screenshot_{i}.png")
        screenshots.append(screenshot)

    cli.stage_screenshots(tuple(s.relative_to(repo) for s in screenshots), repo)

    staged_files = set(get_staged_files(repo))
    assert len(staged_files) == 50
    for i in range(50):
        assert f"screenshot_{i}.png" in staged_files
