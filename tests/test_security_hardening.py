"""
Tests for security hardening features (PERSO-270).

Tests decompression bomb protection and non-bypassable size limit enforcement.
"""

import pytest
from PIL import Image
from wslshot.cli import (
    HARD_MAX_FILE_SIZE_BYTES,
    HARD_MAX_TOTAL_SIZE_BYTES,
    MAX_IMAGE_PIXELS,
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
