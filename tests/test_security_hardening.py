"""
Tests for security hardening features.

Tests decompression bomb protection, non-bypassable size limit enforcement,
and TOCTOU race condition protection.
"""

import os

import pytest
from PIL import Image

from wslshot.cli import (
    HARD_MAX_FILE_SIZE_BYTES,
    HARD_MAX_TOTAL_SIZE_BYTES,
    MAX_IMAGE_PIXELS,
    SecurityError,
    create_directory_safely,
    get_size_limits,
    validate_image_file,
)


class TestDecompressionBombHardening:
    """Tests for decompression bomb protection."""

    def test_pixel_limit_constant_matches_pillow(self):
        """Verify MAX_IMAGE_PIXELS matches Pillow's threshold."""
        assert MAX_IMAGE_PIXELS == 89_478_485
        # Pillow's default: Image.MAX_IMAGE_PIXELS (89,478,485 pixels)

    def test_small_image_passes(self, tmp_path):
        """Images well under pixel limit should pass validation."""
        img_path = tmp_path / "small.png"
        # 1920x1080 = 2,073,600 pixels (well under 89M limit)
        img = Image.new("RGB", (1920, 1080), color="blue")
        img.save(img_path)

        # Should not raise
        assert validate_image_file(img_path) is True

    def test_4k_image_passes(self, tmp_path):
        """4K resolution images should pass (well under limit)."""
        img_path = tmp_path / "4k.png"
        # 3840x2160 = 8,294,400 pixels (well under 89M limit)
        img = Image.new("RGB", (3840, 2160), color="red")
        img.save(img_path)

        assert validate_image_file(img_path) is True

    def test_image_near_pixel_limit_passes(self, tmp_path):
        """Images just under the pixel limit should pass."""
        img_path = tmp_path / "near_limit.png"
        # Use dimensions that give ~88M pixels (under 89,478,485)
        # 9400 * 9400 = 88,360,000 pixels (just under limit)
        img = Image.new("RGB", (9400, 9400), color="green")
        img.save(img_path)

        assert validate_image_file(img_path) is True

    def test_image_over_pixel_limit_rejected(self, tmp_path):
        """Images exceeding pixel limit should be rejected."""
        img_path = tmp_path / "over_limit.png"
        # 9500 * 9500 = 90,250,000 pixels (over 89,478,485 limit)
        img = Image.new("RGB", (9500, 9500), color="yellow")
        img.save(img_path)

        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        error_msg = str(exc_info.value)
        assert "too large" in error_msg.lower()
        # Error caught by DecompressionBombWarning, mentions pixel limit
        assert "89,478,485" in error_msg or "pixel" in error_msg.lower()

    def test_error_message_shows_pixel_count(self, tmp_path):
        """Error message should reference pixel limits."""
        img_path = tmp_path / "huge.png"
        # Create oversized image
        img = Image.new("RGB", (10000, 10000), color="purple")
        img.save(img_path)

        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        error_msg = str(exc_info.value)
        # Error mentions decompression bomb and pixel limit
        assert "too large" in error_msg.lower()
        assert "pixel" in error_msg.lower()

    def test_error_message_shows_limit(self, tmp_path):
        """Error message should include the maximum pixel limit."""
        img_path = tmp_path / "oversized.png"
        img = Image.new("RGB", (9500, 9500), color="orange")
        img.save(img_path)

        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        error_msg = str(exc_info.value)
        assert "89,478,485" in error_msg  # Formatted limit
        assert "pixel" in error_msg.lower() or "exceeds" in error_msg.lower()

    def test_decompression_bomb_warning_promoted_to_error(self, tmp_path):
        """DecompressionBombWarning should be treated as error."""
        img_path = tmp_path / "bomb.png"
        # Create image that triggers decompression bomb warning
        img = Image.new("RGB", (9500, 9500), color="red")
        img.save(img_path)

        # Should raise ValueError, not just warn
        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        assert "too large" in str(exc_info.value).lower()

    def test_rectangular_image_over_limit_rejected(self, tmp_path):
        """Non-square images exceeding pixel limit should be rejected."""
        img_path = tmp_path / "rectangle.png"
        # 12000 * 8000 = 96,000,000 pixels (over limit)
        img = Image.new("RGB", (12000, 8000), color="cyan")
        img.save(img_path)

        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        error_msg = str(exc_info.value)
        assert "too large" in error_msg.lower()
        assert "pixel" in error_msg.lower()


class TestHardSizeLimitEnforcement:
    """Tests for non-bypassable hard ceiling enforcement."""

    def test_hard_ceiling_constants_defined(self):
        """Hard ceiling constants should be correctly defined."""
        assert HARD_MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024  # 50MB
        assert HARD_MAX_TOTAL_SIZE_BYTES == 200 * 1024 * 1024  # 200MB

    def test_config_below_ceiling_respected(self):
        """Config values below hard ceilings should be honored."""
        config = {"max_file_size_mb": 10, "max_total_size_mb": 50}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == 10 * 1024 * 1024  # 10MB
        assert total_limit == 50 * 1024 * 1024  # 50MB

    def test_config_above_file_ceiling_clamped(self):
        """File limit above hard ceiling should be clamped to 50MB."""
        config = {"max_file_size_mb": 100, "max_total_size_mb": 200}
        file_limit, _ = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES  # Clamped to 50MB
        assert file_limit == 50 * 1024 * 1024

    def test_config_above_total_ceiling_clamped(self):
        """Total limit above hard ceiling should be clamped to 200MB."""
        config = {"max_file_size_mb": 50, "max_total_size_mb": 500}
        _, total_limit = get_size_limits(config)

        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES  # Clamped to 200MB
        assert total_limit == 200 * 1024 * 1024

    def test_config_both_above_ceiling_clamped(self):
        """Both limits above ceilings should be clamped."""
        config = {"max_file_size_mb": 200, "max_total_size_mb": 1000}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES  # 50MB
        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES  # 200MB

    def test_disabled_total_limit_applies_hard_ceiling(self):
        """Zero total limit should apply hard ceiling, not None."""
        config = {"max_file_size_mb": 50, "max_total_size_mb": 0}
        _, total_limit = get_size_limits(config)

        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES
        assert total_limit is not None  # Not unlimited!

    def test_negative_total_limit_applies_hard_ceiling(self):
        """Negative total limit should apply hard ceiling."""
        config = {"max_file_size_mb": 50, "max_total_size_mb": -1}
        _, total_limit = get_size_limits(config)

        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES
        assert total_limit is not None

    def test_zero_file_limit_uses_default_clamped(self):
        """Zero file limit should use default (50MB ceiling)."""
        config = {"max_file_size_mb": 0, "max_total_size_mb": 200}
        file_limit, _ = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES

    def test_missing_config_keys_use_defaults(self):
        """Missing config keys should use default hard ceilings."""
        config = {}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES
        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES

    def test_invalid_config_types_use_defaults(self):
        """Invalid config value types should use defaults."""
        config = {"max_file_size_mb": "invalid", "max_total_size_mb": None}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES
        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES

    def test_float_config_values_work(self):
        """Float config values should work correctly."""
        config = {"max_file_size_mb": 25.5, "max_total_size_mb": 100.5}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == int(25.5 * 1024 * 1024)
        assert total_limit == int(100.5 * 1024 * 1024)

    def test_extreme_config_values_clamped(self):
        """Extremely large config values should be clamped."""
        config = {"max_file_size_mb": 999999, "max_total_size_mb": 999999}
        file_limit, total_limit = get_size_limits(config)

        assert file_limit == HARD_MAX_FILE_SIZE_BYTES
        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES


class TestIntegrationSecurityHardening:
    """Integration tests for security hardening."""

    def test_oversized_file_rejected_despite_high_config(self, tmp_path):
        """File over hard ceiling rejected even with high config limit."""
        # Create a file that would be under config limit but over hard ceiling
        img_path = tmp_path / "51mb.png"
        # Create ~51MB image (over 50MB hard ceiling)
        # For a PNG, we need lots of unique data to reach 51MB
        # 7500x7500 RGB image ≈ 169MB uncompressed, compresses to ~15-20MB
        # Use pattern to reduce compression, increase file size
        img = Image.new("RGB", (8000, 8000))
        pixels = img.load()
        # Create noise pattern to reduce PNG compression
        for y in range(8000):
            for x in range(8000):
                pixels[x, y] = ((x * y) % 256, (x + y) % 256, (x - y) % 256)

        # Save with minimal compression
        img.save(img_path, compress_level=0)

        # Verify file is actually over 50MB
        file_size = img_path.stat().st_size
        if file_size < HARD_MAX_FILE_SIZE_BYTES:
            pytest.skip(f"Generated file only {file_size} bytes, need >50MB")

        # Even with high config limit (100MB), hard ceiling (50MB) applies
        config_limit = 100 * 1024 * 1024  # 100MB config
        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path, max_size_bytes=config_limit)

        assert "too large" in str(exc_info.value).lower()

    def test_dimension_bomb_rejected_despite_small_file_size(self, tmp_path):
        """Dimension bombs rejected even if file size is small."""
        img_path = tmp_path / "dimension_bomb.png"
        # Create image with huge dimensions but small file size
        # Solid color compresses well
        img = Image.new("RGB", (9500, 9500), color="white")
        img.save(img_path, optimize=True)

        # Verify file is small (should be under 1MB due to compression)
        file_size = img_path.stat().st_size
        assert file_size < 1 * 1024 * 1024  # Confirm < 1MB

        # Should be rejected for dimensions, not file size
        with pytest.raises(ValueError) as exc_info:
            validate_image_file(img_path)

        error_msg = str(exc_info.value)
        assert "too large" in error_msg.lower()
        # Should mention pixels, not file size
        assert ("9500" in error_msg) or ("pixel" in error_msg.lower())

    def test_aggregate_limit_enforced_when_disabled_in_config(self):
        """Hard ceiling applies even when user disables aggregate limit."""
        # User sets max_total_size_mb to 0 (disable), but hard ceiling still applies
        config = {"max_file_size_mb": 50, "max_total_size_mb": 0}
        _, total_limit = get_size_limits(config)

        # Should not be None (unlimited), should be hard ceiling
        assert total_limit == HARD_MAX_TOTAL_SIZE_BYTES
        assert total_limit == 200 * 1024 * 1024

    def test_legitimate_large_images_still_pass(self, tmp_path):
        """Legitimate large images (8K resolution) should pass."""
        img_path = tmp_path / "8k.png"
        # 8K resolution: 7680x4320 = 33,177,600 pixels (well under 89M)
        img = Image.new("RGB", (7680, 4320), color="blue")
        img.save(img_path)

        # Should pass validation
        assert validate_image_file(img_path) is True

    def test_ultra_wide_screenshot_passes(self, tmp_path):
        """Ultra-wide monitor screenshots should pass."""
        img_path = tmp_path / "ultrawide.png"
        # 5120x1440 (super ultrawide) = 7,372,800 pixels
        img = Image.new("RGB", (5120, 1440), color="gray")
        img.save(img_path)

        assert validate_image_file(img_path) is True


class TestToctouProtection:
    """Tests for TOCTOU race condition protection (CWE-367)."""

    def test_creates_new_directory(self, tmp_path):
        """New directory should be created with specified permissions."""
        new_dir = tmp_path / "new_directory"
        old_umask = os.umask(0)
        try:
            result = create_directory_safely(new_dir, mode=0o700)
        finally:
            os.umask(old_umask)

        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()
        assert (new_dir.stat().st_mode & 0o777) == 0o700

    def test_creates_nested_directories(self, tmp_path):
        """Nested directories should be created."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        result = create_directory_safely(nested_dir, mode=0o755)

        assert result == nested_dir
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_accepts_existing_safe_directory(self, tmp_path):
        """Existing directory owned by current user should be accepted."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir(mode=0o755)

        result = create_directory_safely(existing_dir, mode=0o755)

        assert result == existing_dir
        assert existing_dir.exists()

    def test_rejects_symlink_directory(self, tmp_path):
        """Symlinked directory should be rejected."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        symlink_dir = tmp_path / "symlink"
        symlink_dir.symlink_to(real_dir)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(symlink_dir, mode=0o755)

        assert "symlink" in str(exc_info.value).lower()

    def test_rejects_broken_symlink(self, tmp_path):
        """Broken symlink (pointing to non-existent target) should be rejected."""
        broken_symlink = tmp_path / "broken_link"
        broken_symlink.symlink_to("/nonexistent/path")

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(broken_symlink, mode=0o755)

        assert "symlink" in str(exc_info.value).lower()

    def test_rejects_file_at_path(self, tmp_path):
        """File at directory path should be rejected."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("content")

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(file_path, mode=0o755)

        assert "not a directory" in str(exc_info.value).lower()

    def test_rejects_directory_wrong_owner(self, tmp_path, monkeypatch):
        """Directory owned by different user should be rejected."""
        # Skip on non-POSIX systems where os.getuid() is not available
        if not hasattr(os, "getuid"):
            pytest.skip("os.getuid() not available on this platform")

        # Skip if running as root (cannot test ownership restrictions)
        if os.getuid() == 0:
            pytest.skip("Cannot test ownership restrictions as root")

        # Create a directory that appears to be owned by a different user
        # We'll mock this by checking the SecurityError path
        # In practice, this would require root to create a different-owner dir
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir(mode=0o755)

        # Patch os.getuid to return a different value
        original_uid = os.getuid()
        monkeypatch.setattr(os, "getuid", lambda: original_uid + 1)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(existing_dir, mode=0o755)

        assert "different user" in str(exc_info.value).lower()

    def test_fixes_unsafe_directory_permissions(self, tmp_path, capsys):
        """Directories with unsafe permissions should be fixed."""
        insecure_dir = tmp_path / "insecure"
        old_umask = os.umask(0)
        try:
            insecure_dir.mkdir(mode=0o777)
        finally:
            os.umask(old_umask)

        result = create_directory_safely(insecure_dir, mode=0o700)

        assert result == insecure_dir
        assert (insecure_dir.stat().st_mode & 0o777) == 0o700

        captured = capsys.readouterr()
        assert "unsafe permissions" in captured.err.lower()
        assert "0o777" in captured.err

    def test_does_not_warn_for_safe_permissions(self, tmp_path, capsys):
        """No warning for directories with safe permissions."""
        safe_dir = tmp_path / "safe"
        safe_dir.mkdir(mode=0o700)

        create_directory_safely(safe_dir, mode=0o700)

        captured = capsys.readouterr()
        assert "unsafe" not in captured.err.lower()

    def test_group_writable_is_unsafe(self, tmp_path, capsys):
        """Group-writable permissions should be fixed."""
        group_write_dir = tmp_path / "group_write"
        old_umask = os.umask(0)
        try:
            group_write_dir.mkdir(mode=0o770)
        finally:
            os.umask(old_umask)

        create_directory_safely(group_write_dir, mode=0o700)

        assert (group_write_dir.stat().st_mode & 0o777) == 0o700
        captured = capsys.readouterr()
        assert "unsafe permissions" in captured.err.lower()

    def test_other_writable_is_unsafe(self, tmp_path, capsys):
        """Other-writable permissions should be fixed."""
        other_write_dir = tmp_path / "other_write"
        old_umask = os.umask(0)
        try:
            other_write_dir.mkdir(mode=0o707)
        finally:
            os.umask(old_umask)

        create_directory_safely(other_write_dir, mode=0o700)

        assert (other_write_dir.stat().st_mode & 0o777) == 0o700
        captured = capsys.readouterr()
        assert "unsafe permissions" in captured.err.lower()

    def test_default_mode_is_755(self, tmp_path):
        """Default mode should be 0o755."""
        new_dir = tmp_path / "default_mode"
        old_umask = os.umask(0)
        try:
            create_directory_safely(new_dir)
        finally:
            os.umask(old_umask)

        assert (new_dir.stat().st_mode & 0o777) == 0o755

    def test_chmod_failure_is_best_effort(self, tmp_path, capsys, monkeypatch):
        """chmod failure should warn but not raise an exception."""
        insecure_dir = tmp_path / "chmod_fail"
        old_umask = os.umask(0)
        try:
            insecure_dir.mkdir(mode=0o777)
        finally:
            os.umask(old_umask)

        # Simulate chmod failure by monkeypatching
        def failing_chmod(self_path, mode, *, follow_symlinks=True):
            raise OSError("Simulated permission denied")

        monkeypatch.setattr(type(insecure_dir), "chmod", failing_chmod)

        # Should NOT raise an exception
        result = create_directory_safely(insecure_dir, mode=0o700)

        assert result == insecure_dir
        captured = capsys.readouterr()
        assert "could not fix directory permissions" in captured.err.lower()

    def test_stat_does_not_follow_symlinks(self, tmp_path):
        """Verification that stat() does not follow symlinks (prevents TOCTOU)."""
        # Create a real directory with different ownership simulation
        real_dir = tmp_path / "real"
        real_dir.mkdir(mode=0o755)

        # Create a symlink pointing to the real directory
        symlink_dir = tmp_path / "symlink"
        symlink_dir.symlink_to(real_dir)

        # The function should reject the symlink, not follow it
        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(symlink_dir, mode=0o755)

        assert "symlink" in str(exc_info.value).lower()

        # Verify the real directory was not modified
        assert real_dir.exists()
        assert real_dir.is_dir()

    def test_rejects_symlink_in_parent_path(self, tmp_path):
        """Symlink in parent directory chain should be rejected."""
        # Create real directory
        real_parent = tmp_path / "real_parent"
        real_parent.mkdir()

        # Create symlink to real parent
        symlink_parent = tmp_path / "symlink_parent"
        symlink_parent.symlink_to(real_parent)

        # Try to create child under symlinked parent
        child_dir = symlink_parent / "child"

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(child_dir, mode=0o755)

        assert "symlink" in str(exc_info.value).lower()

        # Verify no directory was created in the real location
        assert not (real_parent / "child").exists()

    def test_rejects_newly_created_directory_wrong_owner(self, tmp_path, monkeypatch):
        """Newly created directories are ownership-checked even with pre-existing parents."""
        # Skip on non-POSIX systems where os.getuid() is not available
        if not hasattr(os, "getuid"):
            pytest.skip("os.getuid() not available on this platform")

        # Skip if running as root (cannot test ownership restrictions)
        if os.getuid() == 0:
            pytest.skip("Cannot test ownership restrictions as root")

        # Create intermediate directory (pre-existing, not ownership-checked)
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir(mode=0o755)

        # Patch os.getuid to simulate wrong ownership for newly created dirs
        original_uid = os.getuid()
        monkeypatch.setattr(os, "getuid", lambda: original_uid + 1)

        # Try to create nested path - should fail on newly created nested dir
        nested = intermediate / "nested"
        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(nested, mode=0o755)

        assert "different user" in str(exc_info.value).lower()

    def test_harden_permissions_false_skips_permission_fixing(self, tmp_path, capsys):
        """harden_permissions=False should skip permission hardening."""
        insecure_dir = tmp_path / "insecure"
        old_umask = os.umask(0)
        try:
            insecure_dir.mkdir(mode=0o777)
        finally:
            os.umask(old_umask)

        # With harden_permissions=False, permissions should NOT be changed
        result = create_directory_safely(insecure_dir, mode=0o700, harden_permissions=False)

        assert result == insecure_dir
        # Permissions should remain unchanged
        assert (insecure_dir.stat().st_mode & 0o777) == 0o777

        captured = capsys.readouterr()
        # No warning should be printed
        assert "unsafe permissions" not in captured.err.lower()

    def test_chmod_notimplementederror_is_caught(self, tmp_path, monkeypatch):
        """NotImplementedError during chmod (TOCTOU race) should raise SecurityError."""
        insecure_dir = tmp_path / "race_condition"
        old_umask = os.umask(0)
        try:
            insecure_dir.mkdir(mode=0o777)
        finally:
            os.umask(old_umask)

        # Simulate the scenario where path becomes a symlink during chmod
        # On Linux, chmod(follow_symlinks=False) on a symlink raises NotImplementedError
        def race_chmod(self_path, mode, *, follow_symlinks=True):
            if not follow_symlinks:
                raise NotImplementedError("chmod: follow_symlinks unavailable on this platform")
            return None

        monkeypatch.setattr(type(insecure_dir), "chmod", race_chmod)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(insecure_dir, mode=0o700)

        assert "symlink" in str(exc_info.value).lower()

    def test_path_disappears_during_creation(self, tmp_path, monkeypatch):
        """Path disappearing between mkdir and lstat should raise SecurityError."""
        target_dir = tmp_path / "disappearing"

        # Keep track of calls to lstat to simulate race condition
        original_lstat = type(target_dir).lstat
        lstat_calls = []

        def racing_lstat(self_path):
            lstat_calls.append(str(self_path))
            # First lstat (existence check) returns FileNotFoundError
            # mkdir succeeds
            # Second lstat (post-creation validation) raises FileNotFoundError
            # (simulating directory removal between mkdir and lstat)
            if (
                str(self_path) == str(target_dir)
                and len([c for c in lstat_calls if c == str(self_path)]) > 1
            ):
                raise FileNotFoundError("Path disappeared")
            return original_lstat(self_path)

        monkeypatch.setattr(type(target_dir), "lstat", racing_lstat)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(target_dir, mode=0o755)

        assert "disappeared" in str(exc_info.value).lower()

    def test_path_disappears_before_chmod(self, tmp_path, monkeypatch):
        """Path disappearing before chmod should raise SecurityError."""
        insecure_dir = tmp_path / "disappearing_chmod"
        old_umask = os.umask(0)
        try:
            insecure_dir.mkdir(mode=0o777)
        finally:
            os.umask(old_umask)

        # Track lstat calls to make it disappear at the right moment
        original_lstat = type(insecure_dir).lstat
        lstat_call_count = [0]

        def racing_lstat(self_path):
            if str(self_path) == str(insecure_dir):
                lstat_call_count[0] += 1
                # First lstat (pre-creation check) - exists
                # Second lstat (post-creation validation) - exists
                # Third lstat (pre-chmod check) - disappears
                if lstat_call_count[0] >= 3:
                    raise FileNotFoundError("Path disappeared before chmod")
            return original_lstat(self_path)

        monkeypatch.setattr(type(insecure_dir), "lstat", racing_lstat)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(insecure_dir, mode=0o700)

        assert "disappeared" in str(exc_info.value).lower()
        assert "chmod" in str(exc_info.value).lower()

    def test_parent_disappears_during_validation(self, tmp_path, monkeypatch):
        """Parent path disappearing during re-validation should raise SecurityError."""
        # Create a nested structure
        parent_dir = tmp_path / "parent"
        parent_dir.mkdir(mode=0o755)
        child_dir = parent_dir / "child"

        original_lstat = type(parent_dir).lstat
        lstat_call_count = [0]

        def racing_lstat(self_path):
            if str(self_path) == str(parent_dir):
                lstat_call_count[0] += 1
                # First call (pre-creation check on parent) - exists
                # Second call (post-creation validation on parent) - exists
                # Third call (re-validation during child processing) - disappears
                if lstat_call_count[0] >= 3:
                    raise FileNotFoundError("Parent disappeared")
            return original_lstat(self_path)

        monkeypatch.setattr(type(parent_dir), "lstat", racing_lstat)

        with pytest.raises(SecurityError) as exc_info:
            create_directory_safely(child_dir, mode=0o755)

        assert "disappeared" in str(exc_info.value).lower()
