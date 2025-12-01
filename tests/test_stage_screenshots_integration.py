from __future__ import annotations

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
