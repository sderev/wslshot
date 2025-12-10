"""
Tests for path sanitization in error messages (PERSO-194, CWE-209).

Verifies that filesystem paths are properly sanitized in error messages
to prevent information disclosure attacks.
"""

import ast
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from wslshot.cli import (
    convert_image_format,
    copy_screenshots,
    fetch,
    format_path_error,
    get_screenshots,
    sanitize_error_message,
    sanitize_path_for_error,
)


class TestSanitizePathForError:
    """Unit tests for sanitize_path_for_error() function."""

    def test_string_path_with_basename(self):
        """String path should show basename with ellipsis."""
        result = sanitize_path_for_error("/home/alice_admin/.secret/key.txt")
        assert result == "<...>/key.txt"

    def test_path_object_with_basename(self):
        """Path object should be converted and show basename."""
        result = sanitize_path_for_error(Path("/home/alice_admin/.secret/key.txt"))
        assert result == "<...>/key.txt"

    def test_hide_basename_completely(self):
        """show_basename=False should completely hide path."""
        result = sanitize_path_for_error("/home/alice_admin/.secret/key.txt", show_basename=False)
        assert result == "<path>"

    def test_relative_path_sanitized(self):
        """Relative paths should be sanitized."""
        result = sanitize_path_for_error("../../../etc/passwd")
        assert result == "<...>/passwd"

    def test_root_path_sanitized(self):
        """Root path should not expose system structure."""
        result = sanitize_path_for_error("/")
        assert result == "<path>"  # No basename

    def test_path_with_spaces(self):
        """Paths with spaces should preserve basename."""
        result = sanitize_path_for_error("/home/user/My Documents/secret.txt")
        assert result == "<...>/secret.txt"

    def test_path_with_unicode(self):
        """Unicode characters in filenames should be preserved."""
        result = sanitize_path_for_error("/home/user/文档/秘密.txt")
        assert result == "<...>/秘密.txt"

    def test_windows_style_path(self):
        """Windows-style paths should only reveal basename."""
        result = sanitize_path_for_error("C:\\Users\\Alice\\Documents\\secret.txt")
        assert result == "<...>/secret.txt"
        assert "Alice" not in result
        assert "Users" not in result

    def test_empty_path_string(self):
        """Empty path should return safe placeholder."""
        result = sanitize_path_for_error("")
        assert result == "<path>"

    def test_no_sensitive_info_in_output(self):
        """Output should not contain usernames or directory structure."""
        sensitive_path = "/home/alice_admin/.ssh/id_rsa"
        result = sanitize_path_for_error(sensitive_path)

        # Ensure NO sensitive information is exposed
        assert "alice_admin" not in result
        assert ".ssh" not in result
        assert "/home/" not in result

        # Only basename should be visible
        assert "id_rsa" in result

    def test_no_directory_structure_leaked(self):
        """Directory structure should not be leaked."""
        result = sanitize_path_for_error("/var/www/app/.env")

        assert "/var/" not in result
        assert "/www/" not in result
        assert "/app/" not in result
        assert result == "<...>/.env"

    def test_basename_parameter_behavior(self):
        """Verify show_basename parameter works correctly."""
        path = "/home/user/config.json"

        # With basename (default)
        with_basename = sanitize_path_for_error(path)
        assert "config.json" in with_basename
        assert "/home/" not in with_basename

        # Without basename
        without_basename = sanitize_path_for_error(path, show_basename=False)
        assert without_basename == "<path>"
        assert "config.json" not in without_basename

    def test_directory_path_with_trailing_slash(self):
        """Directory paths with trailing slashes should be handled."""
        result = sanitize_path_for_error("/home/user/screenshots/")
        # Path object treats trailing slash, name will be empty
        # Should fall back to <path>
        assert result in ["<...>/screenshots", "<path>"]

    def test_hidden_file_sanitized(self):
        """Hidden files (dotfiles) should show basename."""
        result = sanitize_path_for_error("/home/user/.bashrc")
        assert result == "<...>/.bashrc"
        assert "/home/" not in result
        assert "user" not in result

    def test_nested_hidden_directories(self):
        """Nested hidden directories should be sanitized."""
        result = sanitize_path_for_error("/home/user/.config/.secrets/api_key.txt")
        assert result == "<...>/api_key.txt"
        assert ".config" not in result
        assert ".secrets" not in result
        assert "/home/" not in result

    def test_path_with_special_characters(self):
        """Paths with special characters should be handled."""
        result = sanitize_path_for_error("/home/user/file (1).txt")
        assert result == "<...>/file (1).txt"
        assert "/home/" not in result

    def test_single_filename_no_directory(self):
        """Single filename without directory should be sanitized."""
        result = sanitize_path_for_error("file.txt")
        assert result == "<...>/file.txt"

    def test_dot_directory(self):
        """Dot directory (.) should be sanitized."""
        # Path(".").name returns empty string, so falls back to <path>
        result = sanitize_path_for_error(".")
        assert result == "<path>"

    def test_double_dot_directory(self):
        """Double dot directory (..) should be sanitized."""
        result = sanitize_path_for_error("..")
        assert result == "<...>/.."


class TestFormattedPathErrors:
    """Unit tests for formatted, sanitized path errors."""

    def test_value_error_preserves_reason_and_sanitizes_path(self):
        """ValueError messages should retain reason and hide structure."""
        error = ValueError("Symlinks are not allowed: /home/alice_admin/.ssh/id_rsa")

        formatted = format_path_error(error)

        assert formatted == "Symlinks are not allowed: <...>/id_rsa"
        assert "alice_admin" not in formatted
        assert ".ssh" not in formatted

    def test_file_not_found_retains_reason_and_hides_structure(self):
        """FileNotFoundError should keep strerror and sanitize the path."""
        error = FileNotFoundError(
            2,
            "No such file or directory",
            "/home/alice_admin/screenshots/latest.png",
        )

        formatted = format_path_error(error)
        assert formatted.startswith("No such file or directory")
        assert "<...>/latest.png" in formatted
        assert "alice_admin" not in formatted
        assert "screenshots" not in formatted

        hidden = format_path_error(error, show_basename=False)
        assert hidden == "No such file or directory: <path>"

    def test_non_path_error_message_is_not_mangled(self):
        """ValueError without path separators should pass through unchanged."""
        error = ValueError("File too large: 70MB (maximum: 50MB)")

        formatted = format_path_error(error)

        assert formatted == "File too large: 70MB (maximum: 50MB)"

    def test_file_not_found_uses_filename2_when_filename_missing(self):
        """filename2 should be sanitized when filename is None."""
        error = FileNotFoundError(2, "No such file or directory")
        error.filename = None
        error.filename2 = "/tmp/private/config.json"

        formatted = format_path_error(error)

        assert formatted.startswith("No such file or directory")
        assert "<...>/config.json" in formatted
        assert "/tmp/private" not in formatted

    def test_nested_colon_message_redacts_path_suffix(self):
        """Only the trailing path segment should remain after sanitization."""
        error = ValueError("Wrapper: inner: /var/secret/data.txt")

        formatted = format_path_error(error)

        assert formatted == "Wrapper: <...>/data.txt"
        assert "/var/secret" not in formatted


class TestFetchErrorMessages:
    """Integration tests to ensure CLI errors sanitize paths."""

    def test_symlink_error_masks_real_path(self, fake_home: Path, tmp_path: Path):
        """`fetch` should not leak absolute paths on symlink errors."""
        runner = CliRunner()

        real_source = tmp_path / "real_source"
        real_source.mkdir()
        destination = tmp_path / "destination"
        destination.mkdir()

        symlink_parent = tmp_path / "alice_admin" / "very" / "private"
        symlink_parent.mkdir(parents=True)
        symlink_source = symlink_parent / "screens"
        symlink_source.symlink_to(real_source)

        result = runner.invoke(
            fetch,
            ["--source", str(symlink_source), "--destination", str(destination)],
            env={"HOME": str(fake_home)},
        )

        assert result.exit_code == 1
        assert "Symlinks are not allowed" in result.output
        assert "<...>/screens" in result.output
        assert "alice_admin" not in result.output
        assert "private" not in result.output
        assert str(tmp_path) not in result.output
        assert str(symlink_source) not in result.output

    def test_convert_error_masks_real_paths(
        self,
        fake_home: Path,
        tmp_path: Path,
        monkeypatch,
    ):
        """`fetch` should redact absolute paths when conversion fails."""
        runner = CliRunner()

        source = tmp_path / "alice_admin" / "screens"
        source.mkdir(parents=True)
        destination = tmp_path / "very" / "private" / "output"
        destination.mkdir(parents=True)

        image_path = source / "secret.png"
        img = Image.new("RGB", (8, 8), color="red")
        img.save(image_path, "PNG")

        def fail_convert(path, target):
            raise ValueError(f"Cannot identify image file {path}")

        monkeypatch.setattr("wslshot.cli.convert_image_format", fail_convert)

        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(destination), "--convert-to", "jpg"],
            env={"HOME": str(fake_home)},
        )

        assert result.exit_code == 1
        assert str(tmp_path) not in result.output
        assert str(source) not in result.output
        assert str(destination) not in result.output
        assert str(image_path) not in result.output
        assert "<...>/screenshot_" in result.output
        assert "secret.png" not in result.output

    def test_unreadable_source_directory_masks_real_path(
        self,
        fake_home: Path,
        tmp_path: Path,
        monkeypatch,
    ):
        """Permission errors while listing source should be sanitized."""
        runner = CliRunner()

        source = tmp_path / "alice_admin" / "screens"
        source.mkdir(parents=True)
        destination = tmp_path / "output"
        destination.mkdir()

        real_scandir = os.scandir

        def fail_scandir(path):
            if Path(path) == source:
                raise PermissionError(13, "Permission denied", str(source))
            return real_scandir(path)

        monkeypatch.setattr("wslshot.cli.os.scandir", fail_scandir)

        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(destination)],
            env={"HOME": str(fake_home)},
        )

        assert result.exit_code == 1
        assert "Permission denied" in result.output
        assert "<...>/screens" in result.output
        assert str(source) not in result.output
        assert str(tmp_path) not in result.output

    def test_copy_failure_masks_paths(
        self,
        fake_home: Path,
        tmp_path: Path,
        monkeypatch,
    ):
        """Copy errors should redact source and destination paths."""
        runner = CliRunner()

        source = tmp_path / "screens"
        source.mkdir()
        destination = tmp_path / "secret" / "output"
        destination.mkdir(parents=True)

        image_path = source / "secret.png"
        img = Image.new("RGB", (8, 8), color="blue")
        img.save(image_path, "PNG")

        def fail_copy(src, dst, *args, **kwargs):
            raise PermissionError(13, "Permission denied", str(dst))

        monkeypatch.setattr("wslshot.cli.shutil.copy", fail_copy)

        result = runner.invoke(
            fetch,
            ["--source", str(source), "--destination", str(destination)],
            env={"HOME": str(fake_home)},
        )

        assert result.exit_code == 1
        assert "Failed to copy screenshot" in result.output
        assert "<...>/secret.png" in result.output
        assert "<...>/screenshot_" in result.output
        assert str(source) not in result.output
        assert str(destination) not in result.output
        assert str(image_path) not in result.output


class TestSanitizeErrorMessage:
    """Unit tests for sanitize_error_message() helper."""

    def test_replaces_all_occurrences_and_windows_paths(self):
        """Windows-style paths should be redacted everywhere they appear."""
        message = (
            "Failed to open C:\\Users\\Alice\\secret.txt; "
            "C:\\Users\\Alice\\secret.txt may be locked."
        )

        sanitized = sanitize_error_message(message, ("C:\\Users\\Alice\\secret.txt",))

        assert sanitized.count("<...>/secret.txt") == 2
        assert "Alice" not in sanitized
        assert "Users" not in sanitized

    def test_message_without_paths_is_unchanged(self):
        """Messages without the provided paths should remain unchanged."""
        message = "Operation failed for unknown reasons"
        sanitized = sanitize_error_message(message, (Path("/tmp/secret/file.txt"),))

        assert sanitized == message


class TestGetScreenshotsErrors:
    """Ensure get_screenshots redacts filesystem paths on OS errors."""

    def test_permission_error_masks_source_directory(self, tmp_path: Path, capsys, monkeypatch):
        """PermissionError during directory scan should redact the source path."""
        source = tmp_path / "very" / "private" / "screens"
        source.mkdir(parents=True)

        def fail_scandir(path):
            raise PermissionError(13, "Permission denied", str(path))

        monkeypatch.setattr("wslshot.cli.os.scandir", fail_scandir)

        with pytest.raises(SystemExit):
            get_screenshots(str(source), 1)

        err_output = capsys.readouterr().err
        assert "Permission denied" in err_output
        assert "<...>/screens" in err_output
        assert str(source) not in err_output
        assert str(tmp_path) not in err_output


class TestCopyAndConvertSanitization:
    """Ensure helper utilities sanitize sensitive filesystem paths."""

    def test_convert_image_format_redacts_destination_path(self, tmp_path: Path, monkeypatch):
        """Conversion errors should hide source and destination paths."""
        sensitive_dir = tmp_path / "very" / "private"
        sensitive_dir.mkdir(parents=True)

        source_path = sensitive_dir / "secret.png"
        source_path.write_bytes(b"fake image")
        new_path = source_path.with_suffix(".jpg")

        class DummyImage:
            mode = "RGB"
            size = (8, 8)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def save(self, path, *args, **kwargs):
                raise OSError(f"Permission denied: '{path}'")

        monkeypatch.setattr("wslshot.cli.Image.open", lambda *args, **kwargs: DummyImage())

        with pytest.raises(ValueError) as excinfo:
            convert_image_format(source_path, "jpg")

        message = str(excinfo.value)
        assert "<...>/secret.png" in message
        assert "<...>/secret.jpg" in message
        assert str(source_path) not in message
        assert str(new_path) not in message

    def test_copy_screenshots_unreadable_file_masks_path(self, capsys, tmp_path: Path):
        """Unreadable file warnings should not leak full paths."""
        sensitive_path = Path("/home/alice_admin/private/screens/secret.png")

        result = copy_screenshots((sensitive_path,), str(tmp_path))

        captured_err = capsys.readouterr().err
        assert result == ()
        assert "<...>/secret.png" in captured_err
        assert "alice_admin" not in captured_err
        assert str(sensitive_path) not in captured_err


class TestRegressionPathSanitization:
    """Regression tests for path sanitization coverage."""

    def test_all_vulnerable_locations_use_sanitization(self):
        """Ensure all 10 vulnerable locations use sanitization."""
        cli_source = Path("wslshot/cli.py").read_text()
        ast_tree = ast.parse(cli_source)

        call_count = 0
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in {
                    "sanitize_path_for_error",
                    "format_path_error",
                }:
                    call_count += 1

        assert call_count >= 10, f"Expected at least 10 sanitization calls, found {call_count}"
