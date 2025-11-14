from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import UUID

import pytest
from wslshot import cli

# ==================== Finding Screenshots Tests ====================


def test_get_screenshots_finds_png_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds PNG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "Screenshot 2024-01-15.png"
    screenshot.touch()

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_jpg_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds JPG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "photo.jpg"
    screenshot.touch()

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_jpeg_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds JPEG files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "image.jpeg"
    screenshot.touch()

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == screenshot


def test_get_screenshots_finds_gif_files(tmp_path: Path) -> None:
    """Test that get_screenshots finds GIF files in the source directory."""
    source = tmp_path / "source"
    source.mkdir()

    screenshot = source / "animated.gif"
    screenshot.touch()

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
    png_file.touch()
    time.sleep(0.01)
    jpg_file.touch()
    time.sleep(0.01)
    jpeg_file.touch()
    time.sleep(0.01)
    gif_file.touch()

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

    oldest.touch()
    time.sleep(0.01)
    middle.touch()
    time.sleep(0.01)
    newest.touch()

    result = cli.get_screenshots(source, count=3)

    assert len(result) == 3
    assert result[0] == newest
    assert result[1] == middle
    assert result[2] == oldest


def test_get_screenshots_returns_exactly_count_files(tmp_path: Path) -> None:
    """Test that get_screenshots returns exactly the requested count of files."""
    source = tmp_path / "source"
    source.mkdir()

    for i in range(10):
        screenshot = source / f"screenshot_{i}.png"
        screenshot.touch()
        time.sleep(0.01)

    result = cli.get_screenshots(source, count=5)

    assert len(result) == 5


def test_get_screenshots_with_count_one_returns_most_recent(tmp_path: Path) -> None:
    """Test that get_screenshots with count=1 returns the single most recent file."""
    source = tmp_path / "source"
    source.mkdir()

    older = source / "older.png"
    newer = source / "newer.png"

    older.touch()
    time.sleep(0.01)
    newer.touch()

    result = cli.get_screenshots(source, count=1)

    assert len(result) == 1
    assert result[0] == newer


def test_get_screenshots_with_count_three_returns_three_most_recent_in_order(
    tmp_path: Path,
) -> None:
    """Test that get_screenshots with count=3 returns three most recent files in descending order."""
    source = tmp_path / "source"
    source.mkdir()

    files = []
    for i in range(5):
        screenshot = source / f"screenshot_{i}.png"
        screenshot.touch()
        files.append(screenshot)
        time.sleep(0.01)

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
    png_file.touch()
    jpg_file.touch()

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


def test_get_screenshots_handles_uppercase_extensions(tmp_path: Path) -> None:
    """Test that get_screenshots does NOT find files with uppercase extensions (.PNG, .JPG)."""
    source = tmp_path / "source"
    source.mkdir()

    # Create lowercase extension files
    lowercase_png = source / "lowercase.png"
    lowercase_jpg = source / "lowercase.jpg"
    lowercase_png.touch()
    lowercase_jpg.touch()

    # Create uppercase extension files (should be ignored based on the code)
    uppercase_png = source / "UPPERCASE.PNG"
    uppercase_jpg = source / "UPPERCASE.JPG"
    uppercase_png.touch()
    uppercase_jpg.touch()

    # The code only globs for lowercase extensions, so uppercase files are ignored
    result = cli.get_screenshots(source, count=2)

    assert len(result) == 2
    assert set(result) == {lowercase_png, lowercase_jpg}


def test_get_screenshots_raises_error_when_no_screenshots_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that get_screenshots raises ValueError with appropriate message when no screenshots exist."""
    source = tmp_path / "source"
    source.mkdir()

    # Mock sys.exit to capture the exit call
    exit_code = []

    def mock_exit(code):
        exit_code.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", mock_exit)

    # Mock click.echo to capture error messages
    error_messages = []

    def mock_echo(msg, err=False):
        if err:
            error_messages.append(msg)

    monkeypatch.setattr(cli.click, "echo", mock_echo)

    # Test that it raises SystemExit
    with pytest.raises(SystemExit):
        cli.get_screenshots(source, count=1)

    assert exit_code == [1]
    assert any("No screenshot found" in msg for msg in error_messages)


def test_get_screenshots_raises_error_when_count_exceeds_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that get_screenshots raises ValueError when requested count exceeds available files."""
    source = tmp_path / "source"
    source.mkdir()

    # Create only 2 files
    for i in range(2):
        screenshot = source / f"screenshot_{i}.png"
        screenshot.touch()

    # Mock sys.exit to capture the exit call
    exit_code = []

    def mock_exit(code):
        exit_code.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", mock_exit)

    # Mock click.echo to capture error messages
    error_messages = []

    def mock_echo(msg, err=False):
        if err:
            error_messages.append(msg)

    monkeypatch.setattr(cli.click, "echo", mock_echo)

    # Try to get 5 screenshots when only 2 exist
    with pytest.raises(SystemExit):
        cli.get_screenshots(source, count=5)

    assert exit_code == [1]
    # Verify the error message mentions both requested and found counts
    assert any(
        "You requested 5 screenshot(s), but only 2 were found" in msg for msg in error_messages
    )


# ==================== Copying Screenshots Tests ====================


def test_copy_screenshots_copies_file_to_destination(tmp_path: Path) -> None:
    """Test that copy_screenshots successfully copies a file to the destination directory."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    screenshot.write_bytes(b"fake image data")

    result = cli.copy_screenshots((screenshot,), destination)

    assert len(result) == 1
    assert result[0].exists()
    assert result[0].parent == destination
    assert result[0].read_bytes() == b"fake image data"


def test_copy_screenshots_generates_unique_uuid_filenames(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that copy_screenshots generates UUID-based filenames for copied files."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    screenshot.write_bytes(b"data")

    # Mock uuid.uuid4 to return a predictable UUID
    fake_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    result = cli.copy_screenshots((screenshot,), destination)

    assert len(result) == 1
    assert result[0].name == f"screenshot_{fake_uuid.hex}.png"


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
        screenshot.write_bytes(b"data")

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
        screenshot.write_bytes(b"data")
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
        assert copied_path.name == f"screenshot_{uuids[i].hex}.png"


def test_copy_screenshots_returns_tuple_of_path_objects(tmp_path: Path) -> None:
    """Test that copy_screenshots returns a tuple of Path objects."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    screenshot = source / "screenshot.png"
    screenshot.write_bytes(b"data")

    result = cli.copy_screenshots((screenshot,), destination)

    assert isinstance(result, tuple)
    assert all(isinstance(path, Path) for path in result)


def test_copy_screenshots_copied_files_exist_and_readable(tmp_path: Path) -> None:
    """Test that copied files exist and are readable."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    content = b"test image content"
    screenshot = source / "screenshot.png"
    screenshot.write_bytes(content)

    result = cli.copy_screenshots((screenshot,), destination)

    assert result[0].exists()
    assert result[0].is_file()
    assert result[0].read_bytes() == content


def test_copy_screenshots_original_files_unchanged(tmp_path: Path) -> None:
    """Test that original files remain unchanged after copying."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    content = b"original content"
    screenshot = source / "screenshot.png"
    screenshot.write_bytes(content)

    # Get original mtime
    original_mtime = screenshot.stat().st_mtime

    cli.copy_screenshots((screenshot,), destination)

    # Verify original file is unchanged
    assert screenshot.exists()
    assert screenshot.read_bytes() == content
    assert screenshot.stat().st_mtime == original_mtime


# ==================== Filename Generation Tests ====================


def test_generate_screenshot_name_with_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .png generates 'screenshot_<uuid>.png'."""
    fake_uuid = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/image.png")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"screenshot_{fake_uuid.hex}.png"


def test_generate_screenshot_name_with_jpg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .jpg generates 'screenshot_<uuid>.jpg'."""
    fake_uuid = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/photo.jpg")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"screenshot_{fake_uuid.hex}.jpg"


def test_generate_screenshot_name_with_jpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .jpeg generates 'screenshot_<uuid>.jpeg'."""
    fake_uuid = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/image.jpeg")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"screenshot_{fake_uuid.hex}.jpeg"


def test_generate_screenshot_name_with_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .gif generates 'animated_<uuid>.gif'."""
    fake_uuid = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/animation.gif")
    result = cli.generate_screenshot_name(screenshot_path)

    assert result == f"animated_{fake_uuid.hex}.gif"


def test_generate_screenshot_name_with_uppercase_gif(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name with .GIF (uppercase) generates 'animated_<uuid>.gif'."""
    fake_uuid = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    screenshot_path = Path("/tmp/ANIMATION.GIF")
    result = cli.generate_screenshot_name(screenshot_path)

    # Extension should be lowercased in output
    assert result == f"animated_{fake_uuid.hex}.gif"


def test_generate_screenshot_name_lowercases_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generate_screenshot_name lowercases the extension in output."""
    fake_uuid = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: fake_uuid)

    # Test with various uppercase/mixed case extensions
    test_cases = [
        (Path("/tmp/image.PNG"), f"screenshot_{fake_uuid.hex}.png"),
        (Path("/tmp/photo.JPG"), f"screenshot_{fake_uuid.hex}.jpg"),
        (Path("/tmp/image.JPEG"), f"screenshot_{fake_uuid.hex}.jpeg"),
        (Path("/tmp/anim.GIF"), f"animated_{fake_uuid.hex}.gif"),
    ]

    for input_path, expected_name in test_cases:
        result = cli.generate_screenshot_name(input_path)
        assert result == expected_name


# ==================== Heapq Optimization Tests ====================


def test_get_screenshots_uses_heapq_nlargest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_screenshots uses heapq.nlargest instead of list.sort for efficiency."""
    import heapq

    source = tmp_path / "source"
    source.mkdir()

    # Create 10 files
    for i in range(10):
        (source / f"screenshot_{i}.png").touch()

    # Track heapq.nlargest calls
    original_nlargest = heapq.nlargest
    nlargest_calls = []

    def tracked_nlargest(*args, **kwargs):
        nlargest_calls.append((args, kwargs))
        return original_nlargest(*args, **kwargs)

    monkeypatch.setattr(heapq, "nlargest", tracked_nlargest)

    # Get 5 screenshots
    cli.get_screenshots(source, count=5)

    # Verify heapq.nlargest was called
    assert len(nlargest_calls) == 1
    assert nlargest_calls[0][0][0] == 5  # First arg should be count=5


def test_get_screenshots_caches_stat_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_screenshots only calls stat() once per file (caching)."""
    source = tmp_path / "source"
    source.mkdir()

    # Create 10 files
    files = []
    for i in range(10):
        file = source / f"screenshot_{i}.png"
        file.touch()
        files.append(file)

    # Track stat calls
    original_stat = Path.stat
    stat_calls = []

    def tracked_stat(self, **kwargs):
        stat_calls.append(str(self))
        # Handle both Python < 3.13 (no follow_symlinks) and >= 3.13 (with follow_symlinks)
        try:
            return original_stat(self, **kwargs)
        except TypeError:
            # Older Python versions don't accept follow_symlinks
            return original_stat(self)

    monkeypatch.setattr(Path, "stat", tracked_stat)

    # Get 5 screenshots
    cli.get_screenshots(source, count=5)

    # Each file should be stat'd exactly once (not multiple times)
    # We expect 10 stat calls (one per file in directory)
    assert len(stat_calls) == 10
    # Verify no duplicate stat calls
    assert len(set(stat_calls)) == 10


def test_get_screenshots_count_exceeds_available(tmp_path: Path) -> None:
    """Test that get_screenshots handles count > available files gracefully."""
    source = tmp_path / "source"
    source.mkdir()

    # Create only 3 files
    for i in range(3):
        (source / f"screenshot_{i}.png").touch()

    # Request 5 files (more than available) - should exit with error
    with pytest.raises(SystemExit):
        cli.get_screenshots(source, count=5)


def test_get_screenshots_empty_directory(tmp_path: Path) -> None:
    """Test that get_screenshots handles empty directory (no screenshots)."""
    source = tmp_path / "source"
    source.mkdir()

    # No screenshots in directory - should exit with error
    with pytest.raises(SystemExit):
        cli.get_screenshots(source, count=1)
