"""Tests for image format conversion functionality."""

from pathlib import Path

import pytest
from PIL import Image

from wslshot.cli import convert_image_format


class TestImageConversion:
    """Test image format conversion feature."""

    def test_convert_png_to_jpg(self, tmp_path: Path) -> None:
        """Test converting PNG to JPG."""
        # Create a test PNG image
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(png_path, "PNG")

        # Convert to JPG
        jpg_path = convert_image_format(png_path, "jpg")

        assert jpg_path.suffix == ".jpg"
        assert jpg_path.exists()
        assert not png_path.exists()  # Original should be removed

        # Verify it's a valid JPG
        with Image.open(jpg_path) as converted:
            assert converted.format == "JPEG"

    def test_convert_jpg_to_png(self, tmp_path: Path) -> None:
        """Test converting JPG to PNG."""
        jpg_path = tmp_path / "test.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(jpg_path, "JPEG")

        png_path = convert_image_format(jpg_path, "png")

        assert png_path.suffix == ".png"
        assert png_path.exists()
        assert not jpg_path.exists()

        with Image.open(png_path) as converted:
            assert converted.format == "PNG"

    def test_convert_rgba_to_jpg(self, tmp_path: Path) -> None:
        """Test converting RGBA PNG to JPG (should handle transparency)."""
        png_path = tmp_path / "test_rgba.png"
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(png_path, "PNG")

        jpg_path = convert_image_format(png_path, "jpg")

        assert jpg_path.exists()
        with Image.open(jpg_path) as converted:
            assert converted.format == "JPEG"
            assert converted.mode == "RGB"  # Should be converted to RGB

    def test_convert_to_webp(self, tmp_path: Path) -> None:
        """Test converting to WebP format."""
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(png_path, "PNG")

        webp_path = convert_image_format(png_path, "webp")

        assert webp_path.suffix == ".webp"
        assert webp_path.exists()

        with Image.open(webp_path) as converted:
            assert converted.format == "WEBP"

    def test_convert_to_gif(self, tmp_path: Path) -> None:
        """Test converting to GIF format."""
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="yellow")
        img.save(png_path, "PNG")

        gif_path = convert_image_format(png_path, "gif")

        assert gif_path.suffix == ".gif"
        assert gif_path.exists()

        with Image.open(gif_path) as converted:
            assert converted.format == "GIF"

    def test_no_conversion_if_same_format(self, tmp_path: Path) -> None:
        """Test that no conversion occurs if already in target format."""
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="yellow")
        img.save(png_path, "PNG")

        result_path = convert_image_format(png_path, "png")

        assert result_path == png_path
        assert png_path.exists()

    def test_invalid_format_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid format raises ValueError."""
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="black")
        img.save(png_path, "PNG")

        with pytest.raises(ValueError, match="Unsupported target format"):
            convert_image_format(png_path, "bmp")

    def test_normalize_jpeg_to_jpg(self, tmp_path: Path) -> None:
        """Test that 'jpeg' is normalized to 'jpg'."""
        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="white")
        img.save(png_path, "PNG")

        result_path = convert_image_format(png_path, "jpeg")

        assert result_path.suffix == ".jpg"

    def test_convert_palette_mode_to_jpg(self, tmp_path: Path) -> None:
        """Test converting palette mode (P) PNG to JPG."""
        png_path = tmp_path / "test_palette.png"
        img = Image.new("P", (100, 100))
        # Add a palette
        palette = []
        for i in range(256):
            palette.extend((i, i, i))  # Grayscale palette
        img.putpalette(palette)
        img.save(png_path, "PNG")

        jpg_path = convert_image_format(png_path, "jpg")

        assert jpg_path.exists()
        with Image.open(jpg_path) as converted:
            assert converted.format == "JPEG"
            assert converted.mode == "RGB"

    def test_convert_la_mode_to_jpg(self, tmp_path: Path) -> None:
        """Test converting LA mode (grayscale with alpha) PNG to JPG."""
        png_path = tmp_path / "test_la.png"
        img = Image.new("LA", (100, 100), color=(128, 255))
        img.save(png_path, "PNG")

        jpg_path = convert_image_format(png_path, "jpg")

        assert jpg_path.exists()
        with Image.open(jpg_path) as converted:
            assert converted.format == "JPEG"
            assert converted.mode == "RGB"

    def test_conversion_preserves_image_dimensions(self, tmp_path: Path) -> None:
        """Test that conversion preserves image dimensions."""
        png_path = tmp_path / "test.png"
        width, height = 150, 200
        img = Image.new("RGB", (width, height), color="purple")
        img.save(png_path, "PNG")

        jpg_path = convert_image_format(png_path, "jpg")

        with Image.open(jpg_path) as converted:
            assert converted.size == (width, height)

    def test_conversion_failure_raises_error(self, tmp_path: Path) -> None:
        """Test that conversion failure raises ValueError."""
        # Create a corrupted file
        corrupt_path = tmp_path / "corrupt.png"
        corrupt_path.write_text("This is not an image")

        with pytest.raises(ValueError, match="Failed to convert image"):
            convert_image_format(corrupt_path, "jpg")
