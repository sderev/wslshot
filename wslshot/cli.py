"""
WSLShot CLI.

This command-line interface allows for efficient management of screenshots
on a Linux VM with Windows as the host OS.

Features:

- Fetch and copy the most recent screenshots using the 'wslshot' command.
- Specify the number of screenshots to be processed with the '--count' option.
- Customize the source directory using '--source'.
- Customize the destination directory using '--destination'.
- Choose your preferred output style (Markdown, HTML, or text) with the '--output-style' option.
- Configure default settings with the 'configure' subcommand.

For detailed usage instructions, use 'wslshot --help' or 'wslshot [command] --help'.
"""

import heapq
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from stat import S_ISREG
from typing import Any

import click
from click_default_group import DefaultGroup
from PIL import Image

MAX_IMAGE_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_IMAGE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
PNG_TRAILER = b"\x00\x00\x00\x00IEND\xAE\x42\x60\x82"
JPEG_TRAILER = b"\xFF\xD9"
GIF_TRAILER = b"\x3B"


def atomic_write_json(path: Path, data: dict, mode: int = 0o600) -> None:
    """
    Write JSON data atomically to prevent corruption.

    The temp file is created in the same directory as the target file
    to ensure atomic rename (same filesystem). On POSIX systems,
    os.replace() is atomic.

    Args:
        path: Path to target file
        data: Dictionary to write as JSON
        mode: File permissions (default 0o600)

    Raises:
        OSError: If write fails
    """
    # Create temp file in same directory (ensures same filesystem)
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}_", suffix=".tmp")

    try:
        # Write to temp file
        with os.fdopen(temp_fd, "w", encoding="UTF-8") as f:
            json.dump(data, f, indent=4)
            f.flush()              # Flush Python buffers to OS
            os.fsync(f.fileno())   # Force OS to write to physical disk

        # Set permissions on temp file
        os.chmod(temp_path, mode)

        # Atomic rename (POSIX guarantees atomicity)
        os.replace(temp_path, str(path))

        # Ensure directory entry is durable
        dir_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            dir_flags |= os.O_DIRECTORY
        dir_fd = os.open(path.parent, dir_flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    except Exception:
        # Cleanup temp file on any error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def resolve_path_safely(path_str: str, check_symlink: bool = True) -> Path:
    """
    Safely resolve a path without following symlinks.

    This function prevents symlink following attacks (CWE-59) by validating
    that neither the target path nor any component in its parent chain is a
    symlink. This protects against attackers creating symlinks to sensitive
    files (SSH keys, credentials) and tricking the application into copying
    them.

    Args:
        path_str: The path to resolve (can include `~` for home directory)
        check_symlink: If True, reject symlinks (default True for security)

    Returns:
        Resolved Path object (absolute path)

    Raises:
        ValueError: If path is a symlink and `check_symlink=True`
        FileNotFoundError: If path doesn't exist

    Example:
        >>> resolve_path_safely("/home/user/screenshots")
        PosixPath('/home/user/screenshots')

        >>> resolve_path_safely("/tmp/symlink_to_ssh_key")
        ValueError: Symlinks are not allowed: /tmp/symlink_to_ssh_key
    """
    # Expand user home directory (~)
    path = Path(path_str).expanduser()

    # Check if the target path itself is a symlink before resolving
    if check_symlink and path.is_symlink():
        raise ValueError(f"Symlinks are not allowed: {path_str}")

    # Validate no symlinks exist in the parent directory chain BEFORE resolving
    # This prevents attacks like: /tmp/link -> /home/user/.ssh, then /tmp/link/id_rsa
    if check_symlink:
        # Check each component in the path hierarchy (before resolution)
        # Start from the path and work up to root
        current = path.absolute()
        while current != current.parent:
            if current.is_symlink():
                raise ValueError(f"Path contains symlink in parent chain: {current}")
            current = current.parent

    # Resolve to absolute path (will follow symlinks if they exist)
    # strict=True ensures the path exists
    resolved = path.resolve(strict=True)

    return resolved


def validate_image_file(
    file_path: Path,
    *,
    max_size_bytes: int | None = None,
    file_size: int | None = None,
) -> bool:
    """
    Validate file is actually an image by checking magic bytes.

    This function prevents file content validation attacks (CWE-434) by
    verifying that files are legitimate images, not malicious scripts or
    executables renamed with image extensions.

    Uses Pillow's `Image.verify()` to check magic bytes and file structure.
    Also enforces a 50MB per-file size limit to prevent DoS attacks.

    Args:
        file_path: Path to file to validate

    Returns:
        bool: True if valid image file

    Raises:
        ValueError: If file is not a valid image or exceeds size limit

    Example:
        >>> validate_image_file(Path("/tmp/screenshot.png"))
        True

        >>> validate_image_file(Path("/tmp/malicious.png"))  # Actually a script
        ValueError: File is not a valid image: malicious.png
    The size check can be overridden for testing or configuration. Passing
    `file_size` avoids re-statting the file when the caller already has that
    information (e.g., during directory scans).
    """
    # Enforce per-file size limit to prevent DoS attacks
    max_size = MAX_IMAGE_FILE_SIZE_BYTES if max_size_bytes is None else max_size_bytes
    try:
        size_value = file_size if file_size is not None else file_path.stat().st_size
    except OSError as e:
        raise ValueError(f"Cannot read file: {file_path.name}") from e

    if max_size is not None and size_value > max_size:
        raise ValueError(
            f"File too large: {size_value / 1024 / 1024:.2f}MB "
            f"(maximum: {max_size / 1024 / 1024:.0f}MB)"
        )

    # Validate magic bytes using Pillow
    try:
        with Image.open(file_path) as img:
            # Read format BEFORE calling verify() - verify() invalidates the image object
            img_format = img.format

            # Check format is supported (PNG, JPEG, GIF)
            if img_format not in ("PNG", "JPEG", "GIF"):
                raise ValueError(
                    f"Unsupported image format: {img_format} "
                    f"(supported: PNG, JPEG, GIF)"
                )

            img.verify()  # Validates magic bytes and basic file structure

        # Reject files with trailing payloads after the format trailer
        file_bytes = file_path.read_bytes()
        if img_format == "PNG" and not file_bytes.endswith(PNG_TRAILER):
            raise ValueError(f"File contains trailing data after PNG trailer: {file_path.name}")
        if img_format == "JPEG" and not file_bytes.endswith(JPEG_TRAILER):
            raise ValueError(f"File contains trailing data after JPEG trailer: {file_path.name}")
        if img_format == "GIF" and not file_bytes.endswith(GIF_TRAILER):
            raise ValueError(f"File contains trailing data after GIF trailer: {file_path.name}")

        return True

    except Image.DecompressionBombError as e:
        # Decompression bombs are images with huge dimensions but small file size
        # (e.g., 1MB file that decompresses to 10GB). Pillow's default limit is
        # 89,478,485 pixels (~178MB at 24-bit color). We catch this separately
        # to provide a clear error message.
        raise ValueError(
            f"Image dimensions too large: {file_path.name} "
            f"(suspected decompression bomb attack)"
        ) from e
    except (OSError, Image.UnidentifiedImageError) as e:
        raise ValueError(f"File is not a valid image: {file_path.name}") from e


def get_size_limits(config: dict[str, Any]) -> tuple[int, int | None]:
    """
    Resolve per-file and aggregate size limits from config (in MB).

    A non-positive aggregate limit disables the total size cap to avoid
    surprising failures for users with very large screenshot batches.
    """
    default_file_limit_mb = MAX_IMAGE_FILE_SIZE_BYTES // (1024 * 1024)
    default_total_limit_mb = MAX_TOTAL_IMAGE_SIZE_BYTES // (1024 * 1024)

    file_limit_mb = config.get("max_file_size_mb", default_file_limit_mb)
    total_limit_mb = config.get("max_total_size_mb", default_total_limit_mb)

    file_limit_bytes = MAX_IMAGE_FILE_SIZE_BYTES
    if isinstance(file_limit_mb, (int, float)) and file_limit_mb > 0:
        file_limit_bytes = int(file_limit_mb * 1024 * 1024)

    total_limit_bytes: int | None = MAX_TOTAL_IMAGE_SIZE_BYTES
    if isinstance(total_limit_mb, (int, float)):
        if total_limit_mb > 0:
            total_limit_bytes = int(total_limit_mb * 1024 * 1024)
        else:
            total_limit_bytes = None

    return file_limit_bytes, total_limit_bytes


def suggest_format(invalid_format: str, valid_formats: list[str]) -> str:
    """Suggest a similar format if user provides invalid input."""
    invalid_lower = invalid_format.lower()

    # Simple similarity check
    suggestions = []
    for fmt in valid_formats:
        if invalid_lower in fmt or fmt in invalid_lower:
            suggestions.append(fmt)
        elif len(invalid_lower) > 2 and any(
            invalid_lower[i : i + 2] in fmt for i in range(len(invalid_lower) - 1)
        ):
            suggestions.append(fmt)

    if suggestions:
        return f"Did you mean: {', '.join(suggestions)}?"
    return ""


@click.group(cls=DefaultGroup, default="fetch", default_if_no_args=True)
@click.version_option(package_name="wslshot")
def wslshot():
    """
    Fetches and copies the latest screenshot(s) from the source to the specified destination.

    Usage:

    - Customize the number of screenshots with --count.
    - Specify source and destination directories with --source and --destination.
    - Customize output style (Markdown, HTML, or text) with --output-style.
    """


@wslshot.command()
@click.option("--source", "-s", help="Specify a custom source directory for this operation.")
@click.option(
    "--destination",
    "-d",
    help="Specify a custom destination directory for this operation.",
)
@click.option(
    "--count",
    "-n",
    default=1,
    type=click.IntRange(min=1),
    help="Specify the number of most recent screenshots to fetch. Defaults to 1.",
)
@click.option(
    "--output-style",
    "output_format",
    help=("Specify the output style (markdown, html, text). Overrides the default set in config."),
)
@click.option(
    "--convert-to",
    "-c",
    type=click.Choice(["png", "jpg", "jpeg", "webp", "gif"], case_sensitive=False),
    help="Convert screenshot(s) to the specified format (png, jpg, webp, gif).",
)
@click.option(
    "--allow-symlinks",
    is_flag=True,
    default=False,
    help="⚠️  Allow symlinks (WARNING: Security risk - only use with trusted paths).",
)
@click.argument("image_path", type=click.Path(exists=True), required=False)
def fetch(source, destination, count, output_format, convert_to, allow_symlinks, image_path):
    """
    Fetches and copies the latest screenshot(s) from the source to the specified destination.

    Args:

    - source: The source directory.
    - destination: The destination directory.
    - count: The number of screenshots to fetch.
    - output: The output format.
    """
    config = read_config(get_config_file_path())

    # Source directory
    if source is None:
        source = config["default_source"]

    try:
        source = resolve_path_safely(source, check_symlink=not allow_symlinks)
    except ValueError as error:
        click.echo(f"{click.style('Security Error:', fg='red')} {error}", err=True)
        if allow_symlinks:
            click.echo("Symlink check was disabled with --allow-symlinks", err=True)
        else:
            click.echo("If you trust this path, use: --allow-symlinks", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            f"{click.style(f'Source directory {source} does not exist.', fg='red')}",
            err=True,
        )
        sys.exit(1)

    # Destination directory
    if destination is None:
        destination = get_destination()

    try:
        destination = resolve_path_safely(destination, check_symlink=not allow_symlinks)
    except ValueError as error:
        click.echo(f"{click.style('Security Error:', fg='red')} {error}", err=True)
        if allow_symlinks:
            click.echo("Symlink check was disabled with --allow-symlinks", err=True)
        else:
            click.echo("If you trust this path, use: --allow-symlinks", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            f"{click.style(f'Destination directory {destination} does not exist.', fg='red')}",
            err=True,
        )
        sys.exit(1)

    # Output format
    if output_format is None:
        output_format = config["default_output_format"]

    if output_format.casefold() not in ("markdown", "html", "text"):
        click.echo(f"Invalid output format: {output_format}", err=True)
        click.echo("Valid options are: markdown, html, text", err=True)
        suggestion = suggest_format(output_format, ["markdown", "html", "text"])
        if suggestion:
            click.echo(suggestion, err=True)
        sys.exit(1)

    # Convert format
    if convert_to is None and config.get("default_convert_to"):
        convert_to = config["default_convert_to"]

    # If the user specified an image path, copy it to the destination directory.
    if image_path:
        try:
            # SECURITY: Validate image_path is not a symlink (PERSO-192 - critical 6th location)
            image_path_resolved = resolve_path_safely(image_path, check_symlink=not allow_symlinks)

            if not str(image_path_resolved).lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                raise ValueError("Invalid image format (supported formats: png, jpg, jpeg, gif).")
        except ValueError as error:
            click.echo(
                f"{click.style('Security Error:', fg='red')} {error}",
                err=True,
            )
            click.echo(f"Source file: {image_path}", err=True)
            if not allow_symlinks:
                click.echo("If you trust this path, use: --allow-symlinks", err=True)
            sys.exit(1)
        except FileNotFoundError as error:
            click.echo(f"{click.style('Error:', fg='red')} Image file not found: {error}", err=True)
            sys.exit(1)

        image_path = (image_path_resolved,)  # For compatibility with copy_screenshots()
        copied_screenshots = copy_screenshots(image_path, destination)
    else:
        # Copy the screenshot(s) to the destination directory.
        source_screenshots = get_screenshots(source, count)
        copied_screenshots = copy_screenshots(source_screenshots, destination)

    # Convert images if --convert-to option is provided
    if convert_to:
        converted_screenshots: tuple[Path, ...] = ()
        for screenshot in copied_screenshots:
            try:
                converted_path = convert_image_format(screenshot, convert_to)
                converted_screenshots += (converted_path,)
            except ValueError as error:
                click.echo(
                    f"{click.style('Failed to convert image:', fg='red')} {screenshot}",
                    err=True,
                )
                click.echo(f"{error}", err=True)
                sys.exit(1)
        copied_screenshots = converted_screenshots

    relative_screenshots: tuple[Path, ...] = ()
    git_root: Path | None = None

    if is_git_repo():
        try:
            git_root = get_git_root()
        except RuntimeError as error:
            click.echo(click.style(str(error), fg="red"), err=True)
        else:
            relative_screenshots = format_screenshots_path_for_git(copied_screenshots, git_root)

            if bool(config["auto_stage_enabled"]) and relative_screenshots:
                stage_screenshots(relative_screenshots, git_root)

    if relative_screenshots:
        print_formatted_path(output_format, relative_screenshots, relative_to_repo=True)
    else:
        print_formatted_path(output_format, copied_screenshots, relative_to_repo=False)


def get_screenshots(source: str, count: int) -> tuple[Path, ...]:
    """
    Get the most recent screenshot(s) from the source directory.

    Args:
    - source: The source directory.
    - count: The number of screenshots to fetch.

    Returns:
    - The screenshot(s)'s path.
    """
    # Get the most recent screenshot(s) from the source directory.
    try:
        # Use scandir for efficient directory iteration (single directory scan)
        # Stat each file exactly once and cache the result
        file_stats = []
        with os.scandir(source) as entries:
            for entry in entries:
                # Check extension before stat (cheap filter)
                if Path(entry.name).suffix in ('.png', '.jpg', '.jpeg', '.gif'):
                    file_path = Path(entry.path)
                    try:
                        # Stat once and check if it's a regular file
                        stat_result = file_path.stat()
                        if S_ISREG(stat_result.st_mode):
                            file_stats.append((file_path, stat_result.st_mtime))
                    except OSError:
                        # Skip files we can't stat (broken symlinks, permission issues, etc.)
                        pass

        # Use heapq for efficient partial sorting: O(N log count) instead of O(N log N)
        top_files = heapq.nlargest(count, file_stats, key=lambda x: x[1])
        screenshots = [file for file, _ in top_files]

        if len(screenshots) == 0:
            raise ValueError("No screenshot found.")

        if len(screenshots) < count:
            raise ValueError(
                f"You requested {count} screenshot(s), but only {len(screenshots)} were found."
            )
    except ValueError as error:
        click.echo(
            f"{click.style('An error occurred while fetching the screenshot(s).', fg='red')}",
            err=True,
        )
        click.echo(f"{error}", err=True)
        click.echo(f"Source directory: {source}\n", err=True)
        sys.exit(1)

    return tuple(screenshots)


def copy_screenshots(screenshots: tuple[Path, ...], destination: str) -> tuple[Path, ...]:
    """
    Copy the screenshot(s) to the destination directory
    and rename them with unique filesystem-friendly names.

    Args:
    - screenshots: A tuple of Path objects representing the screenshot(s) to copy.
    - destination: The path to the destination directory.

    Returns:
    - A tuple of Path objects representing the new locations of the copied screenshot(s).
    """
    copied_screenshots: tuple[Path, ...] = ()

    for screenshot in screenshots:
        new_screenshot_name = generate_screenshot_name(screenshot)
        new_screenshot_path = Path(destination) / new_screenshot_name
        shutil.copy(screenshot, new_screenshot_path)
        copied_screenshots += (Path(destination) / new_screenshot_name,)

    return copied_screenshots


def generate_screenshot_name(screenshot_path: Path) -> str:
    """
    Produce a filesystem-friendly name for a copied screenshot.
    """
    suffix = screenshot_path.suffix.lower()
    unique_fragment = uuid.uuid4().hex

    if suffix == ".gif":
        return f"animated_{unique_fragment}{suffix}"

    return f"screenshot_{unique_fragment}{suffix}"


def convert_image_format(source_path: Path, target_format: str) -> Path:
    """
    Convert an image to a different format.

    Args:
    - source_path: Path to the source image file.
    - target_format: Target format (png, jpg, jpeg, webp, gif).

    Returns:
    - Path to the converted image (replaces original).

    Raises:
    - ValueError: If conversion fails or format is unsupported.
    """
    target_format = target_format.lower().replace(".", "")

    # Normalize jpeg to jpg
    if target_format == "jpeg":
        target_format = "jpg"

    # Validate target format
    supported_formats = {"png", "jpg", "webp", "gif"}
    if target_format not in supported_formats:
        raise ValueError(
            f"Unsupported target format: {target_format}. "
            f"Supported formats: {', '.join(sorted(supported_formats))}"
        )

    # If already in target format, no conversion needed
    if source_path.suffix.lower().replace(".", "") == target_format:
        return source_path

    try:
        with Image.open(source_path) as img:
            # Convert RGBA to RGB for JPEG (JPEG doesn't support transparency)
            if target_format == "jpg" and img.mode in ("RGBA", "LA", "P"):
                # Create white background
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = rgb_img

            # Create new filename with target extension
            new_path = source_path.with_suffix(f".{target_format}")

            # Save with appropriate format
            if target_format == "jpg":
                img.save(new_path, "JPEG", quality=95, optimize=True)
            elif target_format == "png":
                img.save(new_path, "PNG", optimize=True)
            elif target_format == "webp":
                img.save(new_path, "WEBP", quality=95)
            elif target_format == "gif":
                img.save(new_path, "GIF", optimize=True)

            # Remove original file if conversion created a new file
            if new_path != source_path:
                source_path.unlink()

            return new_path

    except Exception as e:
        raise ValueError(f"Failed to convert image: {e}") from e


def stage_screenshots(screenshots: tuple[Path, ...], git_root: Path) -> None:
    """
    Automatically stage the screenshot(s) if the destination is a Git repo.

    Args:
    - screenshots: The screenshot(s).
    - git_root: The git repository root path.
    """
    if not screenshots:
        return

    try:
        # Try batch staging first for performance
        subprocess.run(
            ["git", "add"] + [str(screenshot) for screenshot in screenshots],
            check=True,
            cwd=git_root,
        )
    except subprocess.CalledProcessError:
        # Batch staging failed - fall back to individual staging
        # This ensures valid files are staged even if some fail
        for screenshot in screenshots:
            try:
                subprocess.run(
                    ["git", "add", str(screenshot)],
                    check=True,
                    cwd=git_root,
                )
            except subprocess.CalledProcessError as e:
                click.echo(
                    f"Warning: Failed to stage screenshot '{screenshot}': {e}",
                    err=True,
                )


def format_screenshots_path_for_git(
    screenshots: tuple[Path, ...], git_root: Path
) -> tuple[Path, ...]:
    """
    Format the screenshot(s)'s path for git.

    Args:

    - screenshots: The screenshot(s).
    """
    formatted_screenshots: tuple[Path, ...] = ()

    for screenshot in screenshots:
        try:
            formatted_screenshots += (Path(screenshot).relative_to(git_root),)
        except ValueError:
            continue

    return formatted_screenshots


def print_formatted_path(
    output_format: str, screenshots: tuple[Path, ...], *, relative_to_repo: bool
) -> None:
    """
    Print the screenshot(s)'s path in the specified format.

    Args:

    - output_format: The output format.
    - screenshots: The screenshot(s).
    """
    for screenshot in screenshots:
        # Adding a '/' to the screenshot path if the destination is a Git repo.
        # This is because the screenshot path is relative to the git repo's.
        screenshot_path = f"/{screenshot}" if relative_to_repo else str(screenshot)

        if output_format.casefold() == "markdown":
            click.echo(f"![{screenshot.name}]({screenshot_path})")

        elif output_format.casefold() == "html":
            click.echo(f'<img src="{screenshot_path}" alt="{screenshot.name}">')

        elif output_format.casefold() == "text":
            click.echo(screenshot_path)

        else:
            click.echo(f"Invalid output format: {output_format}", err=True)
            sys.exit(1)


def get_config_file_path() -> Path:
    """
    Create the configuration file.
    """
    config_file_path = Path.home() / ".config" / "wslshot" / "config.json"
    config_file_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_file_path.exists():
        # Write default config without interactive prompts
        default_config = {
            "default_source": "",
            "default_destination": "",
            "auto_stage_enabled": False,
            "default_output_format": "markdown",
            "default_convert_to": None,
        }
        atomic_write_json(config_file_path, default_config, mode=0o600)

    return config_file_path


def read_config(config_file_path: Path) -> dict[str, Any]:
    """
    Read the configuration file.

    If the configuration file does not exist, a default configuration file is created.

    Args:
        config_file_path: The path to the configuration file.

    Returns:
        The configuration file as a dictionary.
    """
    try:
        with open(config_file_path, "r", encoding="UTF-8") as file:
            config = json.load(file)

    except json.JSONDecodeError:
        write_config(config_file_path)
        with open(config_file_path, "r", encoding="UTF-8") as file:
            config = json.load(file)

    return config


def write_config(config_file_path: Path) -> None:
    """
    Write the configuration file.

    Args:
        config_file_path: The path to the configuration file.
    """

    # Read the current configuration file if it exists.
    try:
        with open(config_file_path, "r", encoding="UTF-8") as file:
            current_config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        current_config = {}

    if current_config:
        click.echo(f"{click.style('Updating the configuration file...', fg='yellow')}")
    else:
        click.echo(f"{click.style('Creating the configuration file...', fg='yellow')}")
    click.echo()

    # Configuration fields
    config_fields = {
        "default_source": ("Enter the path for the default source directory", ""),
        "default_destination": (
            "Enter the path for the default destination directory",
            "",
        ),
        "auto_stage_enabled": (
            "Automatically stage screenshots when copying to a git repository?",
            False,
        ),
        "default_output_format": (
            "Enter the default output format (markdown, html, text)",
            "markdown",
        ),
        "default_convert_to": (
            "Enter the default conversion format (png, jpg, webp, gif, or leave empty for none)",
            None,
        ),
    }

    # Prompt the user for configuration values.
    config = {}
    for field, (message, default) in config_fields.items():
        if field in ["default_source", "default_destination"]:
            config[field] = get_validated_directory_input(field, message, current_config, default)
        elif field == "auto_stage_enabled":
            config[field] = get_config_boolean_input(field, message, current_config, default)
        elif field == "default_output_format":
            config[field] = get_validated_input(
                field,
                message,
                current_config,
                default,
                options=["markdown", "html", "text"],
            )
        elif field == "default_convert_to":
            value = get_config_input(field, message, current_config, default or "")
            # Normalize: empty string or whitespace-only to None
            if value and value.strip():
                config[field] = value.strip().lower()
            else:
                config[field] = None
        else:
            config[field] = get_config_input(field, message, current_config, default)

    # Writing configuration to file
    try:
        atomic_write_json(config_file_path, config)
    except FileNotFoundError as error:
        click.echo(f"Failed to write configuration file: {error}", err=True)
        sys.exit(1)

    if current_config:
        click.echo(f"{click.style('Configuration file updated', fg='green')}")
    else:
        click.echo(f"{click.style('Configuration file created', fg='green')}")


def get_config_input(field, message, current_config, default="") -> str:
    existing = current_config.get(field, default)
    return click.prompt(
        click.style(message, fg="blue"),
        type=str,
        default=existing,
        show_default=True,
    )


def get_config_boolean_input(field, message, current_config, default=False) -> bool:
    existing = current_config.get(field, default)
    return click.confirm(
        click.style(message, fg="blue"),
        default=existing,
    )


def get_validated_directory_input(field, message, current_config, default) -> str:
    while True:
        directory = get_config_input(field, message, current_config, default)

        # If no value is provided, use the default (that is, an empty string).
        if not directory.strip():
            return default

        try:
            return str(resolve_path_safely(directory))
        except ValueError as error:
            click.echo(
                click.style(f"Security Error: {error}", fg="red"),
                err=True,
            )
        except FileNotFoundError as error:
            click.echo(
                click.style(f"Invalid {field.replace('_', ' ')}: {error}", fg="red"),
                err=True,
            )
        finally:
            click.echo()


def get_validated_input(field, message, current_config, default="", options=None) -> str:
    existing = current_config.get(field, default)

    while True:
        value = click.prompt(
            click.style(message, fg="blue"),
            type=str,
            default=existing,
            show_default=True,
        )

        if options and value.lower() not in options:
            click.echo(
                click.style(
                    f"Invalid option for {field.replace('_', ' ')}. Please choose from {', '.join(options)}.",
                    fg="red",
                )
            )
            continue

        return value


def set_default_source(source_str: str) -> None:
    """
    Set the default source directory.

    Args:
        source: The default source directory.
    """
    try:
        source: str = str(resolve_path_safely(source_str))
    except ValueError as error:
        click.echo(click.style(f"Security Error: {error}", fg="red"), err=True)
        sys.exit(1)
    except FileNotFoundError as error:
        click.echo(click.style(f"Invalid source directory: {error}", fg="red"), err=True)
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_source"] = source

    atomic_write_json(config_file_path, config)


def set_default_destination(destination_str: str) -> None:
    """
    Set the default destination directory.

    Args:
        destination: The default destination directory.
    """
    try:
        destination: str = str(resolve_path_safely(destination_str))
    except ValueError as error:
        click.echo(click.style(f"Security Error: {error}", fg="red"), err=True)
        sys.exit(1)
    except FileNotFoundError as error:
        click.echo(click.style(f"Invalid destination directory: {error}", fg="red"), err=True)
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_destination"] = destination

    atomic_write_json(config_file_path, config)


def get_destination() -> Path:
    """
    Get the destination directory.

    Returns:
        The destination directory.
    """
    if is_git_repo():
        return get_git_repo_img_destination()

    config = read_config(get_config_file_path())
    if config["default_destination"]:
        return Path(config["default_destination"])

    return Path.cwd()


def is_git_repo() -> bool:
    """
    Check if the current directory is a Git repository.

    Returns:
        True if the current directory is a Git repository, False otherwise.
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False

    return True


def get_git_root() -> Path:
    """
    Get the absolute path to the current git repository root.
    """
    try:
        git_root_bytes = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Failed to get git root directory.") from error

    return Path(git_root_bytes.strip().decode("utf-8")).resolve()


def get_git_repo_img_destination() -> Path:
    """
    Get the destination directory for a Git repository.

    Returns:
        The destination directory for a Git repository.
    """
    try:
        git_root = get_git_root()
    except RuntimeError as error:
        sys.exit(str(error))

    if (git_root / "img").exists():
        destination = git_root / "img"
    elif (git_root / "images").exists():
        destination = git_root / "images"
    elif (git_root / "assets" / "img").exists():
        destination = git_root / "assets" / "img"
    elif (git_root / "assets" / "images").exists():
        destination = git_root / "assets" / "images"
    else:
        destination = git_root / "assets" / "images"
        destination.mkdir(parents=True, exist_ok=True)

    return destination


def set_auto_stage(auto_stage_enabled: bool) -> None:
    """
    Set whether screenshots are automatically staged when copied to a Git repository.

    Args:
        auto_stage_enabled: Whether screenshots are automatically staged when copied to a Git repo.
    """
    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["auto_stage_enabled"] = auto_stage_enabled

    atomic_write_json(config_file_path, config)


def set_default_output_format(output_format: str) -> None:
    """
    Set the default output format.

    Args:
        output_format: The default output format.
    """
    if output_format.casefold() not in ["markdown", "html", "text"]:
        click.echo(click.style(f"Invalid output format: {output_format}", fg="red"), err=True)
        click.echo("Valid options are: markdown, html, text", err=True)
        suggestion = suggest_format(output_format, ["markdown", "html", "text"])
        if suggestion:
            click.echo(click.style(suggestion, fg="yellow"), err=True)
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_output_format"] = output_format.casefold()

    atomic_write_json(config_file_path, config)


def set_default_convert_to(convert_format: str | None) -> None:
    """
    Set the default image conversion format.

    Args:
        convert_format: The default conversion format (png, jpg, webp, gif, or None).
    """
    if convert_format and convert_format.strip():
        convert_format = convert_format.lower()
        if convert_format not in ["png", "jpg", "jpeg", "webp", "gif"]:
            click.echo(
                click.style(f"Invalid conversion format: {convert_format}", fg="red"),
                err=True,
            )
            click.echo("Valid options are: png, jpg, webp, gif", err=True)
            sys.exit(1)
    else:
        convert_format = None

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_convert_to"] = convert_format

    atomic_write_json(config_file_path, config)


@wslshot.command()
@click.option("--source", "-s", help="Specify the default source directory for this operation.")
@click.option(
    "--destination",
    "-d",
    help="Specify the default destination directory for this operation.",
)
@click.option(
    "--auto-stage-enabled",
    type=bool,
    help=("Control whether screenshots are automatically staged when copied to a git repository."),
)
@click.option(
    "--output-style",
    "output_format",
    help="Set the default output style (markdown, html, text).",
)
@click.option(
    "--convert-to",
    "-c",
    type=click.Choice(["png", "jpg", "jpeg", "webp", "gif"], case_sensitive=False),
    help="Set the default image conversion format.",
)
def configure(source, destination, auto_stage_enabled, output_format, convert_to):
    """
    Set the default source directory, control automatic staging, and set the default output style.

    Usage:

    - Specify the default source directory with --source.

    - Control whether screenshots are automatically staged with --auto-stage.

    - Set the default output style (markdown, html, text) with --output-style.

    ___

    The source directory must be a shared folder between Windows and your Linux VM:

    - If you are using WSL, you can choose the 'Screenshots' folder in your 'Pictures' directory. (e.g., /mnt/c/users/...)

    - For VM users, you should configure a shared folder between Windows and the VM before proceeding.
    """
    # When no options are specified, ask the user for their preferences.
    if all(x is None for x in (source, destination, auto_stage_enabled, output_format, convert_to)):
        write_config(get_config_file_path())

    # Otherwise, set the specified options.
    if source:
        set_default_source(source)

    if destination:
        set_default_destination(destination)

    if auto_stage_enabled is not None:
        set_auto_stage(auto_stage_enabled)

    if output_format:
        set_default_output_format(output_format)

    if convert_to is not None:
        set_default_convert_to(convert_to)
