from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from conftest import create_test_image

from wslshot import cli
from wslshot.exceptions import ScreenshotNotFoundError

# ==================== Finding Screenshots Tests ====================


def test_get_screenshots_finds_png_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds PNG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "Screenshot 2024-01-15.png"
    create_test_image(screenshot)

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_jpg_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds JPG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "photo.jpg"
    create_test_image(screenshot)

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_jpeg_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds JPEG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "image.jpeg"
    create_test_image(screenshot)

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_gif_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds GIF files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "animated.gif"
    create_test_image(screenshot)

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_multiple_extensions(tmp_path: Path) -> None:
    """Test that get_screenshots finds files with different extensions together."""
    source = tmp_path / "source"
    source.mkdir()

    png_file = source / "image1.png"
    jpg_file = source / "image2.jpg"
    jpeg_file = source / "image3.jpeg"
    gif_file = source / "image4.gif"

    # Create files with different timestamps
    base_time = 1700000000
    create_test_image(png_file)
    os.utime(png_file, (base_time, base_time))
    create_test_image(jpg_file)
    os.utime(jpg_file, (base_time + 2, base_time + 2))
    create_test_image(jpeg_file)
    os.utime(jpeg_file, (base_time + 4, base_time + 4))
    create_test_image(gif_file)
    os.utime(gif_file, (base_time + 6, base_time + 6))

    result = cli.get_screenshots(source, count=4)

    assert len(result) == 4
    assert set(result) == {png_file, jpg_file, jpeg_file, gif_file}


def test_get_screenshots_sorts_by_modification_time(tmp_path: Path) -> None:
    """Test that get_screenshots returns files sorted by modification time (most recent first)."""
    source = tmp_path / "source"
    source.mkdir()

    # Create files with explicit timestamps
    oldest = source / "oldest.png"
    middle = source / "middle.png"
    newest = source / "newest.png"

    base_time = 1700000000
    create_test_image(oldest)
    os.utime(oldest, (base_time, base_time))
    create_test_image(middle)
    os.utime(middle, (base_time + 2, base_time + 2))
    create_test_image(newest)
    os.utime(newest, (base_time + 4, base_time + 4))

    result = cli.get_screenshots(source, count=3)

    assert len(result) == 3
    assert result[0] == newest
    assert result[1] == middle
    assert result[2] == oldest


def test_get_screenshots_returns_exactly_count_files(tmp_path: Path) -> None:
    """Test that get_screenshots returns exactly the requested count of files."""
    source = tmp_path / "source"
    source.mkdir()

    base_time = 1700000000
    for i in range(10):
        screenshot = source / f"screenshot_{i}.png"
        create_test_image(screenshot)
        timestamp = base_time + (i * 2)
        os.utime(screenshot, (timestamp, timestamp))

    result = cli.get_screenshots(source, count=5)

    assert len(result) == 5


def test_get_screenshots_with_count_one_returns_most_recent(tmp_path: Path) -> None:
    """Test that get_screenshots with count=1 returns the single most recent file."""
    source = tmp_path / "source"
    source.mkdir()

    older = source / "older.png"
    newer = source / "newer.png"

    base_time = 1700000000
    create_test_image(older)
    os.utime(older, (base_time, base_time))
    create_test_image(newer)
    os.utime(newer, (base_time + 2, base_time + 2))

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == newer


def test_get_screenshots_with_count_three_returns_three_most_recent_in_order(
    tmp_path: Path,
) -> None:
    """Test that get_screenshots with count=3 returns three most recent files in descending order."""
    source = tmp_path / "source"
    source.mkdir()

    base_time = 1700000000
    files = []
    for i in range(5):
        screenshot = source / f"screenshot_{i}.png"
        create_test_image(screenshot)
        timestamp = base_time + (i * 2)
        os.utime(screenshot, (timestamp, timestamp))
        files.append(screenshot)

    result = cli.get_screenshots(source, count=3)

    assert len(result) == 3
    # Most recent three in reverse chronological order
    assert result[0] == files[4]
    assert result[1] == files[3]
    assert result[2] == files[2]


def test_get_screenshots_ignores_non_image_files(tmp_path: Path) -> None:
    """Test that get_screenshots ignores non-image files like .txt and .pdf."""
    source = tmp_path / "source"
    source.mkdir()

    # Create image files
    png_file = source / "image.png"
    jpg_file = source / "photo.jpg"
    create_test_image(png_file)
    create_test_image(jpg_file)

    # Create non-image files
    txt_file = source / "readme.txt"
    pdf_file = source / "document.pdf"
    mp4_file = source / "video.mp4"
    txt_file.touch()
    pdf_file.touch()
    mp4_file.touch()

    result = cli.get_screenshots(source, count=2)

    assert len(result) == 2
    assert set(result) == {png_file, jpg_file}


def test_get_screenshots_finds_uppercase_extensions(tmp_path: Path) -> None:
    """Test that get_screenshots finds files with uppercase extensions (.PNG, .JPG)."""
    source = tmp_path / "source"
    source.mkdir()

    # Create mixed-case extension files
    lowercase_png = source / "lowercase.png"
    uppercase_jpg = source / "UPPERCASE.JPG"
    mixed_jpeg = source / "MiXeD.JpEg"

    base_time = 1700000000
    create_test_image(lowercase_png)
    os.utime(lowercase_png, (base_time, base_time))
    create_test_image(uppercase_jpg)
    os.utime(uppercase_jpg, (base_time + 2, base_time + 2))
    create_test_image(mixed_jpeg)
    os.utime(mixed_jpeg, (base_time + 4, base_time + 4))

    result = cli.get_screenshots(source, count=3)

    assert len(result) == 3
    assert set(result) == {lowercase_png, uppercase_jpg, mixed_jpeg}


def test_get_screenshots_case_insensitive_all_formats(tmp_path: Path) -> None:
    """Test that all supported formats work with various case combinations."""
    source = tmp_path / "source"
    source.mkdir()

    # Test all combinations
    test_files = [
        source / "image.png",
        source / "image.PNG",
        source / "image.jpg",
        source / "image.JPG",
        source / "image.jpeg",
        source / "image.JPEG",
        source / "image.gif",
        source / "image.GIF",
    ]

    base_time = 1700000000
    for index, file in enumerate(test_files):
        create_test_image(file)
        timestamp = base_time + (index * 2)
        os.utime(file, (timestamp, timestamp))

    result = cli.get_screenshots(source, count=8)

    assert len(result) == 8
    assert set(result) == set(test_files)


def test_get_screenshots_raises_error_when_no_screenshots_found(tmp_path: Path) -> None:
    """Test that get_screenshots raises ScreenshotNotFoundError when no screenshots exist."""
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(ScreenshotNotFoundError, match="No screenshots found"):
        cli.get_screenshots(source, count=1)


def test_get_screenshots_raises_error_when_count_exceeds_available(tmp_path: Path) -> None:
    """Test that get_screenshots raises ScreenshotNotFoundError when count exceeds available files."""
    source = tmp_path / "source"
    source.mkdir()

    # Create only 2 files
    for i in range(2):
        screenshot = source / f"screenshot_{i}.png"
        create_test_image(screenshot)

    # Try to get 5 screenshots when only 2 exist
    with pytest.raises(ScreenshotNotFoundError) as exc_info:
        cli.get_screenshots(source, count=5)

    # Verify the error message mentions both requested and found counts
    assert "Only 2 screenshot(s) found" in str(exc_info.value)
    assert "you asked for 5" in str(exc_info.value)


# ==================== Copying Screenshots Tests ====================


def test_copy_screenshots_copies_file_to_destination(tmp_path: Path) -> None:
    """Test that copy_screenshots successfully copies a file to the destination directory."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    create_test_image(screenshot)

    result = cli.copy_screenshots((screenshot,), destination)

    assert len(result) == 1
    assert result[0].exists()
    assert result[0].parent == destination
    # Verify it's a copy (different path, same content)
    assert result[0].read_bytes() == screenshot.read_bytes()


def test_copy_screenshots_generates_unique_uuid_filenames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that copy_screenshots generates UUID-based filenames for copied files."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    create_test_image(screenshot)

    # Mock uuid.uuid4 to return a predictable UUID
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    result = cli.copy_screenshots((screenshot,), destination)

    assert len(result) == 1
    assert result[0].name == f"{fake_uuid.hex}.png"


def test_copy_screenshots_preserves_file_extensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that copy_screenshots preserves the original file extension."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    # Test different extensions
    extensions = [".png", ".jpg", ".jpeg", ".gif"]
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    for ext in extensions:
        screenshot = source / f"image{ext}"
        create_test_image(screenshot)

        result = cli.copy_screenshots((screenshot,), destination)

        assert result[0].suffix == ext


def test_copy_screenshots_handles_multiple_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that copy_screenshots can handle multiple files in one call."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshots = []
    for i in range(3):
        screenshot = source / f"screenshot_{i}.png"
        create_test_image(screenshot)
        screenshots.append(screenshot)

    # Mock uuid.uuid4 to return different UUIDs for each call
    uuid_counter = [0]
    uuids = [
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("22222222-2222-2222-2222-222222222222"),
        UUID("33333333-3333-3333-3333-333333333333"),
    ]

    def mock_uuid():
        uuid = uuids[uuid_counter[0]]
        uuid_counter[0] += 1
        return uuid

    monkeypatch.setattr(cli.uuid, "uuid4", mock_uuid)

    result = cli.copy_screenshots(tuple(screenshots), destination)

    assert len(result) == 3
    for i, copied_path in enumerate(result):
        assert copied_path.exists()
        assert copied_path.parent == destination
        assert copied_path.name == f"{uuids[i].hex}.png"


def test_copy_screenshots_returns_tuple_of_path_objects(tmp_path: Path) -> None:
    """Test that copy_screenshots returns a tuple of Path objects."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    create_test_image(screenshot)

    result = cli.copy_screenshots((screenshot,), destination)

    assert isinstance(result, tuple)
    assert all(isinstance(path, Path) for path in result)


def test_copy_screenshots_copied_files_exist_and_readable(tmp_path: Path) -> None:
    """Test that copied files exist and are readable."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    create_test_image(screenshot)

    result = cli.copy_screenshots((screenshot,), destination)

    assert result[0].exists()
    assert result[0].is_file()
    # Verify content matches original
    assert result[0].read_bytes() == screenshot.read_bytes()


def test_copy_screenshots_original_files_unchanged(tmp_path: Path) -> None:
    """Test that original files remain unchanged after copying."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    create_test_image(screenshot)

    # Get original content and mtime
    original_content = screenshot.read_bytes()
    original_mtime = screenshot.stat().st_mtime

    cli.copy_screenshots((screenshot,), destination)

    # Verify original file is unchanged
    assert screenshot.exists()
    assert screenshot.read_bytes() == original_content
    assert screenshot.stat().st_mtime == original_mtime


def test_copy_screenshots_honors_aggregate_cap(tmp_path: Path, capsys) -> None:
    """copy_screenshots enforces configurable total size limit without huge fixtures."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshots = []
    sizes: list[int] = []

    for i in range(3):
        screenshot = source / f"small_{i}.png"
        create_test_image(screenshot)
        sizes.append(screenshot.stat().st_size)
        screenshots.append(screenshot)

    # Set limit so only the first file fits
    size_limit = sizes[0] + sizes[1] - 1

    copied = cli.copy_screenshots(
        tuple(screenshots),
        destination,
        max_total_size_bytes=size_limit,
    )

    captured = capsys.readouterr()
    assert "Total size limit" in captured.err
    assert len(copied) == 1, "Should stop copying once limit is crossed"
    assert copied[0].exists()


def test_copy_screenshots_respects_disabled_aggregate_cap(tmp_path: Path, capsys) -> None:
    """Disabling total size cap copies all files and emits no cap warning."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshots = []
    for i in range(3):
        screenshot = source / f"screenshot_{i}.png"
        create_test_image(screenshot)
        screenshots.append(screenshot)

    copied = cli.copy_screenshots(
        tuple(screenshots),
        destination,
        max_total_size_bytes=None,
    )

    captured = capsys.readouterr()
    assert "Total size limit" not in captured.err
    assert len(copied) == 3
    for path in copied:
        assert path.exists()


# ==================== Filename Generation Tests ====================


def test_generate_screenshot_name_with_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .png generates '<uuid>.png'."""
    fake_uuid = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/image.png")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"{fake_uuid.hex}.png"


def test_generate_screenshot_name_with_jpg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .jpg generates '<uuid>.jpg'."""
    fake_uuid = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/photo.jpg")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"{fake_uuid.hex}.jpg"


def test_generate_screenshot_name_with_jpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .jpeg generates '<uuid>.jpeg'."""
    fake_uuid = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/image.jpeg")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"{fake_uuid.hex}.jpeg"


def test_generate_screenshot_name_with_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .gif generates '<uuid>.gif'."""
    fake_uuid = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/animation.gif")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"{fake_uuid.hex}.gif"


def test_generate_screenshot_name_with_uppercase_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .GIF (uppercase) generates '<uuid>.gif'."""
    fake_uuid = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/ANIMATION.GIF")
    result = cli.generate_screenshot_name(screenshot_path)

    # Extension should be lowercased in output
    assert result == f"{fake_uuid.hex}.gif"


def test_generate_screenshot_name_lowercases_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name lowercases the extension in output."""
    fake_uuid = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    # Test with various uppercase/mixed case extensions
    test_cases = [
        (Path("/tmp/image.PNG"), f"{fake_uuid.hex}.png"),
        (Path("/tmp/photo.JPG"), f"{fake_uuid.hex}.jpg"),
        (Path("/tmp/image.JPEG"), f"{fake_uuid.hex}.jpeg"),
        (Path("/tmp/anim.GIF"), f"{fake_uuid.hex}.gif"),
    ]

    for input_path, expected_name in test_cases:
        result = cli.generate_screenshot_name(input_path)
        assert result == expected_name


# ==================== Candidate Validation Tests ====================


def test_get_screenshots_skips_stale_invalid_files_without_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Older invalid files should not emit warnings when newer valid files satisfy the request."""
    source = tmp_path / "source"
    source.mkdir()

    stale_invalid = source / "stale.png"
    stale_invalid.write_text("not an image", encoding="UTF-8")
    os.utime(stale_invalid, (1700000000, 1700000000))

    newest_valid = source / "newest.png"
    create_test_image(newest_valid)
    os.utime(newest_valid, (1700000010, 1700000010))

    result = cli.get_screenshots(source, count=1)
    captured = capsys.readouterr()

    assert result == (newest_valid,)
    assert "Skipping invalid image file" not in captured.err


def test_get_screenshots_warns_for_invalid_newest_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invalid files should still warn when they are among the newest candidates."""
    source = tmp_path / "source"
    source.mkdir()

    newest_invalid = source / "newest.png"
    newest_invalid.write_text("not an image", encoding="UTF-8")
    os.utime(newest_invalid, (1700000020, 1700000020))

    second_newest_valid = source / "valid.png"
    create_test_image(second_newest_valid)
    os.utime(second_newest_valid, (1700000010, 1700000010))

    result = cli.get_screenshots(source, count=1)
    captured = capsys.readouterr()

    assert result == (second_newest_valid,)
    assert "Skipping invalid image file" in captured.err


def test_get_screenshots_count_exceeds_available(tmp_path: Path) -> None:
    """Test that get_screenshots handles count > available files gracefully."""
    source = tmp_path / "source"
    source.mkdir()

    # Create only 3 files
    for i in range(3):
        create_test_image(source / f"screenshot_{i}.png")

    # Request 5 files (more than available) - should raise ScreenshotNotFoundError
    with pytest.raises(ScreenshotNotFoundError):
        cli.get_screenshots(source, count=5)


def test_get_screenshots_empty_directory(tmp_path: Path) -> None:
    """Test that get_screenshots handles empty directory (no screenshots)."""
    source = tmp_path / "source"
    source.mkdir()

    # No screenshots in directory - should raise ScreenshotNotFoundError
    with pytest.raises(ScreenshotNotFoundError):
        cli.get_screenshots(source, count=1)
