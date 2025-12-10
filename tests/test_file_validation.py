"""
Test suite for file content validation (PERSO-193 - CWE-434).

This test suite ensures that the application properly validates file content
using magic bytes instead of relying solely on file extensions. This prevents
attackers from renaming malicious files (scripts, executables) with image
extensions and having them processed by the application.

Security Issue: CWE-434 (Unrestricted Upload of File with Dangerous Type)
CVSS Score: 7.5 (High)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from wslshot.cli import validate_image_file


class TestValidateImageFile:
    """Test the validate_image_file() function with various inputs."""

    def test_valid_png_passes_validation(self, tmp_path: Path) -> None:
        """Valid PNG file should pass validation."""
        img_path = tmp_path / "valid.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path, "PNG")

        assert validate_image_file(img_path) is True

    def test_valid_jpeg_passes_validation(self, tmp_path: Path) -> None:
        """Valid JPEG file should pass validation."""
        img_path = tmp_path / "valid.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG")

        assert validate_image_file(img_path) is True

    def test_valid_gif_passes_validation(self, tmp_path: Path) -> None:
        """Valid GIF file should pass validation."""
        img_path = tmp_path / "valid.gif"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(img_path, "GIF")

        assert validate_image_file(img_path) is True

    def test_text_file_with_png_extension_rejected(self, tmp_path: Path) -> None:
        """Text file renamed to .png should be rejected."""
        malicious = tmp_path / "malicious.png"
        malicious.write_text("This is a text file, not an image!\n")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_shell_script_with_jpg_extension_rejected(self, tmp_path: Path) -> None:
        """Shell script renamed to .jpg should be rejected."""
        malicious = tmp_path / "script.jpg"
        malicious.write_text("#!/bin/bash\nrm -rf /\n")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_python_script_with_jpeg_extension_rejected(self, tmp_path: Path) -> None:
        """Python script renamed to .jpeg should be rejected."""
        malicious = tmp_path / "script.jpeg"
        malicious.write_text("#!/usr/bin/env python3\nimport sys\nprint('malicious code')\n")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_binary_executable_with_gif_extension_rejected(self, tmp_path: Path) -> None:
        """Binary executable renamed to .gif should be rejected."""
        malicious = tmp_path / "executable.gif"
        # ELF magic bytes for Linux executable
        malicious.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_html_file_with_png_extension_rejected(self, tmp_path: Path) -> None:
        """HTML file renamed to .png should be rejected."""
        malicious = tmp_path / "page.png"
        malicious.write_text("<html><body><h1>Not an image</h1></body></html>")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_json_file_with_jpg_extension_rejected(self, tmp_path: Path) -> None:
        """JSON file renamed to .jpg should be rejected."""
        malicious = tmp_path / "data.jpg"
        malicious.write_text('{"malicious": "data"}')

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(malicious)

    def test_empty_file_with_image_extension_rejected(self, tmp_path: Path) -> None:
        """Empty file with image extension should be rejected."""
        empty = tmp_path / "empty.png"
        empty.touch()

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(empty)

    def test_corrupted_png_header_rejected(self, tmp_path: Path) -> None:
        """File with corrupted PNG header should be rejected."""
        corrupted = tmp_path / "corrupted.png"
        # Invalid PNG magic bytes
        corrupted.write_bytes(b"\x89PNG\x0d\x0a\x1a\xff" + b"\x00" * 100)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(corrupted)

    def test_partial_png_file_rejected(self, tmp_path: Path) -> None:
        """Incomplete PNG file should be rejected."""
        partial = tmp_path / "partial.png"
        # Valid PNG header but incomplete data
        partial.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(partial)

    def test_png_with_trailing_payload_rejected(self, tmp_path: Path) -> None:
        """PNG with data appended after IEND should be rejected."""
        img_path = tmp_path / "payload.png"
        img = Image.new("RGB", (10, 10), color="red")
        img.save(img_path, "PNG")

        img_path.write_bytes(img_path.read_bytes() + b"# appended script")

        with pytest.raises(ValueError, match="trailing data"):
            validate_image_file(img_path)

    def test_file_overrides_allow_small_size_limit(self, tmp_path: Path) -> None:
        """Per-file size check can be configured for testing."""
        img_path = tmp_path / "tiny.png"
        img = Image.new("RGB", (10, 10), color="blue")
        img.save(img_path, "PNG")

        file_size = img_path.stat().st_size
        assert (
            validate_image_file(
                img_path,
                max_size_bytes=file_size + 1,
                file_size=file_size,
            )
            is True
        )

    def test_file_over_limit_rejected(self, tmp_path: Path) -> None:
        """File over custom limit should be rejected."""
        img_path = tmp_path / "small.png"
        img = Image.new("RGB", (20, 20), color="blue")
        img.save(img_path, "PNG")

        file_size = img_path.stat().st_size
        with pytest.raises(ValueError, match="File too large"):
            validate_image_file(
                img_path,
                max_size_bytes=file_size - 1,
                file_size=file_size,
            )

    def test_error_message_shows_file_size(self, tmp_path: Path) -> None:
        """Error message for oversized file should show the actual size."""
        oversized = tmp_path / "big.png"
        img = Image.new("RGB", (10, 10))
        img.save(oversized, "PNG")

        simulated_size = 51 * 1024 * 1024  # 51MB

        with pytest.raises(ValueError, match=r"51\.00MB"):
            validate_image_file(
                oversized,
                max_size_bytes=50 * 1024 * 1024,
                file_size=simulated_size,
            )

    def test_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        """Attempting to validate non-existent file should raise error."""
        nonexistent = tmp_path / "does_not_exist.png"

        with pytest.raises(ValueError, match="Cannot read file"):
            validate_image_file(nonexistent)

    def test_bmp_format_rejected(self, tmp_path: Path) -> None:
        """BMP format should be rejected (not in supported list)."""
        bmp_path = tmp_path / "image.bmp"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(bmp_path, "BMP")

        # Even though it's a valid image, BMP is not in the allowed formats
        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_image_file(bmp_path)

    def test_webp_format_rejected(self, tmp_path: Path) -> None:
        """WebP format should be rejected (not in supported list)."""
        webp_path = tmp_path / "image.webp"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(webp_path, "WEBP")

        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_image_file(webp_path)

    def test_tiff_format_rejected(self, tmp_path: Path) -> None:
        """TIFF format should be rejected (not in supported list)."""
        tiff_path = tmp_path / "image.tiff"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(tiff_path, "TIFF")

        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_image_file(tiff_path)

    def test_rgba_png_passes_validation(self, tmp_path: Path) -> None:
        """PNG with alpha channel should pass validation."""
        img_path = tmp_path / "rgba.png"
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(img_path, "PNG")

        assert validate_image_file(img_path) is True

    def test_grayscale_jpeg_passes_validation(self, tmp_path: Path) -> None:
        """Grayscale JPEG should pass validation."""
        img_path = tmp_path / "grayscale.jpg"
        img = Image.new("L", (100, 100), color=128)
        img.save(img_path, "JPEG")

        assert validate_image_file(img_path) is True

    def test_animated_gif_passes_validation(self, tmp_path: Path) -> None:
        """Animated GIF should pass validation."""
        img_path = tmp_path / "animated.gif"

        # Create simple animated GIF (2 frames)
        frames = []
        frames.append(Image.new("RGB", (100, 100), color="red"))
        frames.append(Image.new("RGB", (100, 100), color="blue"))

        frames[0].save(
            img_path,
            "GIF",
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )

        assert validate_image_file(img_path) is True

    def test_small_1x1_image_passes_validation(self, tmp_path: Path) -> None:
        """Very small 1x1 pixel image should pass validation."""
        img_path = tmp_path / "tiny.png"
        img = Image.new("RGB", (1, 1), color="white")
        img.save(img_path, "PNG")

        assert validate_image_file(img_path) is True

    def test_large_valid_image_under_limit_passes(self, tmp_path: Path) -> None:
        """Large valid image under 50MB should pass."""
        img_path = tmp_path / "large.png"
        # Create a reasonably large image (should be well under 50MB)
        img = Image.new("RGB", (4000, 4000), color="red")
        img.save(img_path, "PNG")

        file_size = img_path.stat().st_size
        assert file_size < 50 * 1024 * 1024  # Verify it's under limit

        assert validate_image_file(img_path) is True

    def test_progressive_jpeg_passes_validation(self, tmp_path: Path) -> None:
        """Progressive JPEG should pass validation."""
        img_path = tmp_path / "progressive.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG", progressive=True)

        assert validate_image_file(img_path) is True

    def test_optimized_png_passes_validation(self, tmp_path: Path) -> None:
        """Optimized PNG should pass validation."""
        img_path = tmp_path / "optimized.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(img_path, "PNG", optimize=True)

        assert validate_image_file(img_path) is True

    def test_zip_file_with_png_extension_rejected(self, tmp_path: Path) -> None:
        """ZIP file renamed to .png should be rejected."""
        zip_file = tmp_path / "archive.png"
        # ZIP magic bytes
        zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(zip_file)

    def test_pdf_file_with_jpg_extension_rejected(self, tmp_path: Path) -> None:
        """PDF file renamed to .jpg should be rejected."""
        pdf_file = tmp_path / "document.jpg"
        # PDF magic bytes
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(pdf_file)

    def test_svg_file_with_png_extension_rejected(self, tmp_path: Path) -> None:
        """SVG file renamed to .png should be rejected."""
        svg_file = tmp_path / "vector.png"
        svg_content = """<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
            <circle cx="50" cy="50" r="40" fill="red"/>
        </svg>"""
        svg_file.write_text(svg_content)

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(svg_file)

    def test_xml_file_with_gif_extension_rejected(self, tmp_path: Path) -> None:
        """XML file renamed to .gif should be rejected."""
        xml_file = tmp_path / "data.gif"
        xml_file.write_text('<?xml version="1.0"?><root><data>test</data></root>')

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(xml_file)

    def test_javascript_file_with_png_extension_rejected(self, tmp_path: Path) -> None:
        """JavaScript file renamed to .png should be rejected."""
        js_file = tmp_path / "malicious.png"
        js_file.write_text("alert('XSS attack!');\nwindow.location='evil.com';")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(js_file)

    def test_csv_file_with_jpg_extension_rejected(self, tmp_path: Path) -> None:
        """CSV file renamed to .jpg should be rejected."""
        csv_file = tmp_path / "data.jpg"
        csv_file.write_text("name,email,password\njohn,john@example.com,secret123")

        with pytest.raises(ValueError, match="not a valid image"):
            validate_image_file(csv_file)

    def test_mixed_case_extension_handled(self, tmp_path: Path) -> None:
        """File with mixed-case extension should work correctly."""
        img_path = tmp_path / "image.PNG"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path, "PNG")

        assert validate_image_file(img_path) is True

    def test_uppercase_extension_handled(self, tmp_path: Path) -> None:
        """File with uppercase extension should work correctly."""
        img_path = tmp_path / "image.JPG"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG")

        assert validate_image_file(img_path) is True
