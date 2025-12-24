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
- Convert screenshots to png, jpg/jpeg, webp, or gif with the '--convert-to' option or a configured default.
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
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISLNK, S_ISREG

import click
from click_default_group import DefaultGroup
from PIL import Image

from wslshot.exceptions import SecurityError

# CLI message prefixes (styled, user-facing)
SECURITY_ERROR_PREFIX = click.style("Security error:", fg="red")
WARNING_PREFIX = click.style("Warning:", fg="yellow")


# ============================================================================
# Constants
# ============================================================================

# File permissions
CONFIG_FILE_PERMISSIONS = 0o600
CONFIG_DIR_PERMISSIONS = 0o700
FILE_PERMISSION_MASK = 0o777

# Output formats
OUTPUT_FORMAT_MARKDOWN = "markdown"
OUTPUT_FORMAT_HTML = "html"
OUTPUT_FORMAT_TEXT = "text"
DEFAULT_OUTPUT_FORMAT = OUTPUT_FORMAT_MARKDOWN
VALID_OUTPUT_FORMATS = (OUTPUT_FORMAT_MARKDOWN, OUTPUT_FORMAT_HTML, OUTPUT_FORMAT_TEXT)
OUTPUT_FORMATS_HELP = ", ".join(VALID_OUTPUT_FORMATS)
LEGACY_OUTPUT_FORMAT_PLAIN_TEXT = "plain_text"

# Git image directory detection (priority order)
GIT_IMAGE_DIRECTORY_PRIORITY = (
    ("img",),
    ("images",),
    ("assets", "img"),
    ("assets", "images"),
)

# Hard maximum limits (non-bypassable security ceilings)
# Config values are clamped to these limits to prevent DoS attacks
HARD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB per file
HARD_MAX_TOTAL_SIZE_BYTES = 200 * 1024 * 1024  # 200MB aggregate

# Default limits (configurable but clamped to hard ceilings)
MAX_IMAGE_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_IMAGE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
# Pillow's decompression bomb warning threshold (89.478M pixels)
# Images exceeding this are potential DoS vectors even if under file size limit
MAX_IMAGE_PIXELS = 89_478_485
PNG_TRAILER = b"\x00\x00\x00\x00IEND\xae\x42\x60\x82"
JPEG_TRAILER = b"\xff\xd9"
GIF_TRAILER = b"\x3b"

# Valid conversion target formats (lowercase, without dot)
VALID_CONVERT_FORMATS = ("png", "jpg", "jpeg", "webp", "gif")

# Supported image file extensions (lowercase)
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")


def normalize_optional_directory(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, Path):
        value = str(value)

    if not isinstance(value, str):
        raise TypeError("Directory path must be a string.")

    if not value.strip():
        return ""

    return str(resolve_path_safely(value))


def normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False

    raise TypeError("Boolean value must be a bool.")


def normalize_output_format(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Output format must be a string.")

    normalized = value.casefold()
    if normalized not in VALID_OUTPUT_FORMATS:
        suggestion = suggest_format(value, list(VALID_OUTPUT_FORMATS))
        valid_options = ", ".join(VALID_OUTPUT_FORMATS)
        message = f"Invalid `--output-style`: {value}. Use one of: {valid_options}."
        if suggestion:
            message = f"{message} {suggestion}"
        raise ValueError(message)

    return normalized


def normalize_default_convert_to(value: object) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError("Conversion format must be a string or None.")

    normalized = value.strip().lower().replace(".", "")
    if not normalized:
        return None

    if normalized not in VALID_CONVERT_FORMATS:
        valid_options = ", ".join(VALID_CONVERT_FORMATS)
        suggestion = suggest_format(normalized, list(VALID_CONVERT_FORMATS))
        message = f"Invalid `--convert-to`: {value}. Use one of: {valid_options}."
        if suggestion:
            message = f"{message} {suggestion}"
        raise ValueError(message)

    return normalized


def normalize_int(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Value must be an int.")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty.")
        return int(stripped)

    raise TypeError("Value must be an int.")


@dataclass(frozen=True)
class ConfigFieldSpec:
    prompt: str
    default: object
    normalize: Callable[[object], object]


CONFIG_FIELD_SPECS: dict[str, ConfigFieldSpec] = {
    "default_source": ConfigFieldSpec(
        prompt="Default source directory",
        default="",
        normalize=normalize_optional_directory,
    ),
    "default_destination": ConfigFieldSpec(
        prompt="Default destination directory",
        default="",
        normalize=normalize_optional_directory,
    ),
    "auto_stage_enabled": ConfigFieldSpec(
        prompt="Auto-stage screenshots with `git add`?",
        default=False,
        normalize=normalize_bool,
    ),
    "default_output_format": ConfigFieldSpec(
        prompt="Default output style (markdown, html, text)",
        default=DEFAULT_OUTPUT_FORMAT,
        normalize=normalize_output_format,
    ),
    "default_convert_to": ConfigFieldSpec(
        prompt="Default conversion format (png, jpg/jpeg, webp, gif). Leave empty for none.",
        default=None,
        normalize=normalize_default_convert_to,
    ),
    "max_file_size_mb": ConfigFieldSpec(
        prompt="Per-file size limit in MB (max 50)",
        default=MAX_IMAGE_FILE_SIZE_BYTES // (1024 * 1024),
        normalize=normalize_int,
    ),
    "max_total_size_mb": ConfigFieldSpec(
        prompt="Max total size in MB per batch (max 200). Use <=0 for 200.",
        default=MAX_TOTAL_IMAGE_SIZE_BYTES // (1024 * 1024),
        normalize=normalize_int,
    ),
}


DEFAULT_CONFIG: dict[str, object] = {
    field: spec.default for field, spec in CONFIG_FIELD_SPECS.items()
}


def _is_interactive_terminal() -> bool:
    """
    Return True when user interaction (prompting) is expected to work.

    We intentionally keep this conservative: when stdin is not a TTY, prompting for
    config values will block CI/CD and scripted runs.
    """
    try:
        return bool(getattr(sys.stdin, "isatty", lambda: False)())
    except Exception:
        return False


def _next_available_backup_path(path: Path, *, suffix: str) -> Path:
    """
    Return an available path for a backup file next to `path`.

    Example: `config.json` -> `config.json.corrupted`, then `.corrupted.1`, ...
    """
    candidate = path.with_name(f"{path.name}{suffix}")
    if not candidate.exists():
        return candidate

    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}{suffix}.{index}")
        if not candidate.exists():
            return candidate

    raise OSError(f"Too many backup files for {path.name}{suffix}")


def _backup_corrupted_file_or_warn(config_file_path: Path) -> None:
    backup_path: Path | None = None
    try:
        backup_path = _next_available_backup_path(config_file_path, suffix=".corrupted")
        config_file_path.replace(backup_path)
    except OSError as backup_error:
        sanitized = sanitize_error_message(
            str(backup_error),
            (config_file_path, backup_path) if backup_path is not None else (config_file_path,),
        )
        click.echo(
            f"{WARNING_PREFIX} Could not back up the corrupted config file: {sanitized}",
            err=True,
        )


def atomic_write_json(path: Path, data: dict, mode: int = CONFIG_FILE_PERMISSIONS) -> None:
    """
    Write JSON data atomically to prevent corruption.

    The temp file is created in the same directory as the target file
    to ensure atomic rename (same filesystem). On POSIX systems,
    os.replace() is atomic.

    Directory fsync is best-effort: if it fails after the atomic rename succeeds,
    a warning is emitted but the function returns successfully. The config is
    updated; only durability across power loss is not guaranteed.

    Args:
        path: Path to target file
        data: Dictionary to write as JSON
        mode: File permissions (default CONFIG_FILE_PERMISSIONS)

    Raises:
        OSError: If temp file creation or atomic rename fails.
        TypeError/ValueError: If JSON encoding fails.
    """
    # Create temp file in same directory (ensures same filesystem)
    temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}_", suffix=".tmp")

    try:
        # Write to temp file
        with os.fdopen(temp_fd, "w", encoding="UTF-8") as f:
            json.dump(data, f, indent=4)
            f.flush()  # Flush Python buffers to OS
            os.fsync(f.fileno())  # Force OS to write to physical disk

        # Set permissions on temp file
        os.chmod(temp_path, mode)

        # Atomic rename (POSIX guarantees atomicity)
        os.replace(temp_path, str(path))

    except Exception:
        # Cleanup temp file on any error before rename
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    # Best-effort directory fsync for durability
    # Config is already updated; failure here only affects durability across power loss
    try:
        dir_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            dir_flags |= os.O_DIRECTORY
        dir_fd = os.open(path.parent, dir_flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as error:
        click.echo(
            f"{WARNING_PREFIX} Config saved but durability not guaranteed: {error}",
            err=True,
        )


def write_config_safely(config_file_path: Path, config_data: dict[str, object]) -> None:
    """
    Write configuration data while enforcing secure permissions.

    Rejects symlinked config paths to prevent privilege escalation via symlink swaps.
    Attempts to fix insecure permissions on existing files (best-effort); if chmod
    fails, the atomic write is still attempted since it creates a fresh file with
    correct permissions.

    Args:
        config_file_path: Path to config file
        config_data: Configuration dictionary to write

    Raises:
        SecurityError: If the config path is a symlink
        OSError: If the atomic write fails
    """
    if config_file_path.is_symlink():
        raise SecurityError("Config file is a symlink; refusing to write for safety.")

    if config_file_path.exists():
        current_perms = config_file_path.stat().st_mode & FILE_PERMISSION_MASK
        if current_perms != CONFIG_FILE_PERMISSIONS:
            click.echo(
                f"{WARNING_PREFIX} Config file permissions were too open ({oct(current_perms)}). "
                f"Resetting to {oct(CONFIG_FILE_PERMISSIONS)}.",
                err=True,
            )
            try:
                config_file_path.chmod(CONFIG_FILE_PERMISSIONS)
            except OSError as error:
                # Best-effort: warn but proceed with atomic write
                # The atomic replace will create a new file with correct permissions
                sanitized = sanitize_error_message(str(error), (config_file_path,))
                click.echo(
                    f"{WARNING_PREFIX} Could not fix permissions ({sanitized}); "
                    "atomic write will replace with secure file.",
                    err=True,
                )

    atomic_write_json(config_file_path, config_data, mode=CONFIG_FILE_PERMISSIONS)


def write_config_or_exit(config_file_path: Path, config_data: dict[str, object]) -> None:
    """
    Persist config changes and present user-friendly failures.
    """
    try:
        write_config_safely(config_file_path, config_data)
    except (FileNotFoundError, SecurityError, OSError) as error:
        sanitized_error = format_path_error(error)
        click.secho(
            f"Error: Failed to write config file: {sanitized_error}",
            fg="red",
            err=True,
        )
        sys.exit(1)


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


def create_directory_safely(
    directory: Path, mode: int = 0o755, *, harden_permissions: bool = True
) -> Path:
    """
    Create directory with TOCTOU protection.

    Creates parent directories iteratively with validation between each step
    to prevent TOCTOU race conditions. Verifies directories are not symlinks,
    owned by current user, and have appropriate permissions.

    Permission Policy:
        When `harden_permissions=True`, this function prevents *insecure*
        permissions (group/other writable, i.e., 0o022 bits set) but does not
        enforce the exact `mode`. For example, an existing 0o755 directory will
        not be tightened to 0o700 since 0o755 is already secure.

    Args:
        directory: Directory path to create
        mode: Permission mode for new directories (default 0o755)
        harden_permissions: If True (default), fix group/other writable
            permissions on the target directory. Set to False for shared
            directories like git-tracked image folders where group-write
            may be intentional.

    Returns:
        The created or verified directory path

    Raises:
        SecurityError: If symlink detected or ownership mismatch

    Note:
        On non-POSIX systems (e.g., Windows), ownership validation is skipped
        since `os.getuid()` is not available.
    """
    # Get absolute path
    directory = directory.absolute()

    # Build list of all path components from root to target
    # We need to validate from shallowest to deepest to prevent TOCTOU
    components = []
    current = directory
    while current != current.parent:
        components.append(current)
        current = current.parent
    components.reverse()  # Now ordered from root to target

    # Track which directories we create (vs already existed)
    created_dirs = set()

    # Check if ownership validation is available (POSIX-only)
    # On Windows, os.getuid() doesn't exist; skip ownership checks there
    can_check_ownership = hasattr(os, "getuid")

    # Create directories one-by-one with validation between each
    # This prevents TOCTOU attacks during mkdir(parents=True)
    for idx, component in enumerate(components):
        # Use lstat to check existence without following symlinks
        # Also detect existing symlinks in the same syscall
        try:
            pre_stat = component.lstat()
            existed_before = True
            # Pre-creation check: detect existing symlinks
            if S_ISLNK(pre_stat.st_mode):
                raise SecurityError(f"Path contains symlink: {sanitize_path_for_error(component)}")
        except FileNotFoundError:
            existed_before = False

        if not existed_before:
            try:
                component.mkdir(mode=mode, exist_ok=False)
                created_dirs.add(component)
            except FileExistsError:
                # Race condition: directory created between lstat() and mkdir()
                # Fall through to post-creation validation
                pass

        # Post-creation validation using lstat (does not follow symlinks)
        # This is the critical security check that replaces is_symlink() + is_dir()
        try:
            stat_info = component.lstat()
        except FileNotFoundError as err:
            raise SecurityError(
                f"Path disappeared during creation: {sanitize_path_for_error(component)}"
            ) from err

        # Check if it's a symlink using the already-fetched stat_info
        # This avoids a TOCTOU race between lstat() and a separate is_symlink() call
        if S_ISLNK(stat_info.st_mode):
            raise SecurityError(f"Path is a symlink: {sanitize_path_for_error(component)}")

        # Use S_ISDIR on lstat result to verify it's a directory without following symlinks
        if not S_ISDIR(stat_info.st_mode):
            raise SecurityError(
                f"Path exists but is not a directory: {sanitize_path_for_error(component)}"
            )

        # Re-validate all parent components to catch TOCTOU attacks
        # An attacker might replace an earlier parent with a symlink
        for parent_idx in range(idx):
            parent = components[parent_idx]
            try:
                parent_stat = parent.lstat()
                if S_ISLNK(parent_stat.st_mode):
                    raise SecurityError(
                        f"Parent path became symlink: {sanitize_path_for_error(parent)}"
                    )
            except FileNotFoundError as err:
                raise SecurityError(
                    f"Parent path disappeared: {sanitize_path_for_error(parent)}"
                ) from err

        # Perform ownership validation for directories we created or the final target
        # Skip ownership check for pre-existing system directories (e.g., /tmp, /home)
        if can_check_ownership and (component in created_dirs or component == directory):
            if stat_info.st_uid != os.getuid():
                raise SecurityError(
                    f"Directory owned by different user (UID {stat_info.st_uid}): "
                    f"{sanitize_path_for_error(component)}"
                )

        # For the final target directory only, optionally fix unsafe permissions
        if harden_permissions and component == directory:
            current_mode = stat_info.st_mode & FILE_PERMISSION_MASK
            if current_mode & 0o022:
                click.echo(
                    f"{WARNING_PREFIX} Directory has unsafe permissions ({oct(current_mode)}). "
                    f"Fixing to {oct(mode)}.",
                    err=True,
                )
                # Re-check symlink before chmod to close TOCTOU window
                # Use lstat + S_ISLNK for consistency with other checks
                try:
                    pre_chmod_stat = directory.lstat()
                    if S_ISLNK(pre_chmod_stat.st_mode):
                        raise SecurityError(
                            f"Path became symlink before chmod: {sanitize_path_for_error(directory)}"
                        )
                except FileNotFoundError as err:
                    raise SecurityError(
                        f"Path disappeared before chmod: {sanitize_path_for_error(directory)}"
                    ) from err
                try:
                    # Use follow_symlinks=False to prevent symlink dereferencing
                    directory.chmod(mode, follow_symlinks=False)
                except NotImplementedError as err:
                    # On Linux, chmod with follow_symlinks=False fails on symlinks.
                    # This indicates a TOCTOU race: path became a symlink after our check.
                    raise SecurityError(
                        f"Path became symlink during chmod: {sanitize_path_for_error(directory)}"
                    ) from err
                except OSError as error:
                    # Best-effort: warn but proceed since ownership check passed
                    sanitized = sanitize_error_message(str(error), (directory,))
                    click.echo(
                        f"{WARNING_PREFIX} Could not fix directory permissions: {sanitized}",
                        err=True,
                    )

    return directory


def sanitize_path_for_error(path: str | Path, *, show_basename: bool = True) -> str:
    """
    Sanitize filesystem paths in error messages (CWE-209 prevention).

    This function prevents CWE-209 (Information Exposure Through Error Message) by
    hiding sensitive path information that could reveal usernames, directory structure,
    or system configuration to attackers.

    Args:
        path: Path to sanitize (string or Path object)
        show_basename: If True, show `<...>/filename`; if False, show `<path>`

    Returns:
        Sanitized path string safe for error messages

    Examples:
        >>> sanitize_path_for_error("/home/alice/.ssh/key.txt")
        '<...>/key.txt'

        >>> sanitize_path_for_error("/home/alice/.ssh/key.txt", show_basename=False)
        '<path>'

    Security Context:
        Without sanitization, error messages like "Source directory /home/alice_admin/.secret
        does not exist" reveal usernames and directory structure to attackers probing the system.
    """
    if isinstance(path, Path):
        path = str(path)

    if not show_basename:
        return "<path>"

    path_str = str(path)
    if not path_str:
        return "<path>"

    # Normalize both POSIX and Windows separators to safely extract basename
    normalized = path_str.replace("\\", "/").rstrip("/")
    basename = normalized.split("/")[-1] if normalized else ""

    if not basename or basename == ".":
        return "<path>"

    return f"<...>/{basename}"


def format_path_error(error: Exception, *, show_basename: bool = True) -> str:
    """
    Format path-related errors with sanitized paths for safe display.

    Keeps user-facing context like "No such file or directory" while ensuring
    filesystem paths are redacted to prevent CWE-209 information disclosure.
    """
    if isinstance(error, FileNotFoundError):
        filename = error.filename or error.filename2
        reason = error.strerror or "Path not found"
        if filename:
            sanitized = sanitize_path_for_error(filename, show_basename=show_basename)
            return f"{reason}: {sanitized}"
        return reason

    message = str(error)
    if ": " in message:
        prefix, path_part = message.split(": ", 1)
        # Only sanitize when the suffix looks like a filesystem path
        if any(sep in path_part for sep in ("/", "\\")):
            sanitized = sanitize_path_for_error(path_part, show_basename=show_basename)
            return f"{prefix}: {sanitized}"

    return message


def sanitize_error_message(
    message: str,
    paths: tuple[str | Path, ...],
    *,
    show_basename: bool = True,
) -> str:
    """
    Replace occurrences of filesystem paths inside an error message with sanitized versions.

    Args:
        message: Error message potentially containing sensitive paths.
        paths: Tuple of paths to sanitize if present in the message.
        show_basename: Whether to reveal the basename when sanitizing.

    Returns:
        Message with sensitive paths redacted.
    """
    sanitized_message = message
    for path in paths:
        sanitized_message = sanitized_message.replace(
            str(path),
            sanitize_path_for_error(path, show_basename=show_basename),
        )
    return sanitized_message


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
            f"File too large: {file_path.name} ({size_value / 1024 / 1024:.2f}MB; "
            f"max {max_size / 1024 / 1024:.0f}MB)"
        )

    # Validate magic bytes using Pillow
    try:
        # Configure Pillow to treat decompression bomb warnings as errors
        # This prevents oversized images (89M+ pixels) from bypassing validation
        warnings.filterwarnings("error", category=Image.DecompressionBombWarning)

        with Image.open(file_path) as img:
            # Read format BEFORE calling verify() - verify() invalidates the image object
            img_format = img.format

            # Check format is supported (PNG, JPEG, GIF)
            if img_format not in ("PNG", "JPEG", "GIF"):
                raise ValueError(
                    f"Unsupported image format: {img_format} (supported: PNG, JPEG, GIF)"
                )

            img.verify()  # Validates magic bytes and basic file structure

        # Re-open image to check dimensions (verify() invalidates the object)
        with Image.open(file_path) as img_check:
            total_pixels = img_check.width * img_check.height
            if total_pixels > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"Image dimensions too large: {img_check.width}x{img_check.height} "
                    f"({total_pixels:,} pixels, maximum: {MAX_IMAGE_PIXELS:,})"
                )

        # Reject files with trailing payloads after the format trailer
        file_bytes = file_path.read_bytes()
        if img_format == "PNG" and not file_bytes.endswith(PNG_TRAILER):
            raise ValueError(f"File contains trailing data after PNG trailer: {file_path.name}")
        if img_format == "JPEG" and not file_bytes.endswith(JPEG_TRAILER):
            raise ValueError(f"File contains trailing data after JPEG trailer: {file_path.name}")
        if img_format == "GIF" and not file_bytes.endswith(GIF_TRAILER):
            raise ValueError(f"File contains trailing data after GIF trailer: {file_path.name}")

        return True

    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        # Decompression bombs are images with huge dimensions but small file size
        # (e.g., 1MB file that decompresses to 10GB). Pillow's default limit is
        # 89,478,485 pixels (~178MB at 24-bit color). We catch this separately
        # to provide a clear error message.
        raise ValueError(
            f"Image dimensions too large: {file_path.name} "
            f"(exceeds {MAX_IMAGE_PIXELS:,} pixel limit, suspected decompression bomb attack)"
        ) from e
    except (OSError, Image.UnidentifiedImageError) as e:
        raise ValueError(f"File is not a valid image: {file_path.name}") from e


def get_size_limits(config: dict[str, object]) -> tuple[int, int | None]:
    """
    Resolve per-file and aggregate size limits from config (in MB).

    Config values are clamped to hard security ceilings (HARD_MAX_*) to prevent
    DoS attacks. Users can set lower limits, but cannot exceed hard maximums.

    A non-positive aggregate limit in config now applies the hard ceiling
    (HARD_MAX_TOTAL_SIZE_BYTES) instead of disabling the check entirely.

    Returns:
        Tuple of (file_limit_bytes, total_limit_bytes)
        - file_limit_bytes: Per-file limit (always enforced, max 50MB)
        - total_limit_bytes: Aggregate limit (max 200MB, never None)
    """
    default_file_limit_mb = MAX_IMAGE_FILE_SIZE_BYTES // (1024 * 1024)
    default_total_limit_mb = MAX_TOTAL_IMAGE_SIZE_BYTES // (1024 * 1024)

    file_limit_mb = config.get("max_file_size_mb", default_file_limit_mb)
    total_limit_mb = config.get("max_total_size_mb", default_total_limit_mb)

    # Calculate requested file limit
    file_limit_bytes = MAX_IMAGE_FILE_SIZE_BYTES
    if isinstance(file_limit_mb, (int, float)) and file_limit_mb > 0:
        file_limit_bytes = int(file_limit_mb * 1024 * 1024)

    # Enforce hard ceiling on per-file limit
    file_limit_bytes = min(file_limit_bytes, HARD_MAX_FILE_SIZE_BYTES)

    # Calculate aggregate limit
    total_limit_bytes: int | None = MAX_TOTAL_IMAGE_SIZE_BYTES
    if isinstance(total_limit_mb, (int, float)):
        if total_limit_mb > 0:
            total_limit_bytes = int(total_limit_mb * 1024 * 1024)
            # Enforce hard ceiling on aggregate limit
            total_limit_bytes = min(total_limit_bytes, HARD_MAX_TOTAL_SIZE_BYTES)
        else:
            # User disabled aggregate limit, but hard ceiling still applies
            total_limit_bytes = HARD_MAX_TOTAL_SIZE_BYTES

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
    Copy screenshots and print their copied paths (defaults to `fetch`).

    \b
    Examples:
      wslshot
      wslshot --count 3
      wslshot "<...>/screenshot.png"
      wslshot configure
    """


@wslshot.command()
@click.option("--source", "-s", help="Source directory for this run (overrides config).")
@click.option(
    "--destination",
    "-d",
    help="Destination directory for this run (overrides config).",
)
@click.option(
    "--count",
    "-n",
    default=1,
    type=click.IntRange(min=1),
    help="How many screenshots to copy (newest first). Default: 1.",
)
@click.option(
    "--output-style",
    "output_format",
    help=(f"Output style for printed paths ({OUTPUT_FORMATS_HELP}; overrides config)."),
)
@click.option(
    "--convert-to",
    "-c",
    type=click.Choice(list(VALID_CONVERT_FORMATS), case_sensitive=False),
    help="Convert copied screenshots to this format (png, jpg/jpeg, webp, gif).",
)
@click.option(
    "--allow-symlinks",
    is_flag=True,
    default=False,
    help="Allow symlinks in paths (security risk; use only with trusted paths).",
)
@click.argument("image_path", type=click.Path(exists=True), required=False)
def fetch(source, destination, count, output_format, convert_to, allow_symlinks, image_path):
    """
    Copy screenshots into the destination directory and print their copied paths.

    \b
    Examples:
      wslshot fetch
      wslshot fetch --count 5
      wslshot fetch --convert-to webp
      wslshot fetch "<...>/screenshot.png"
    """
    config = read_config(get_config_file_path_or_exit())
    max_file_size_bytes, max_total_size_bytes = get_size_limits(config)

    # Source directory
    if source is None:
        source = config["default_source"]

    try:
        source = resolve_path_safely(source, check_symlink=not allow_symlinks)
    except ValueError as error:
        sanitized_error = format_path_error(error)
        click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_error}", err=True)
        click.echo("Hint: If you trust this path, rerun with `--allow-symlinks`.", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.secho(
            f"Error: Source directory not found: {sanitize_path_for_error(source)}",
            fg="red",
            err=True,
        )
        click.echo("Hint: Set `--source` or run `wslshot configure`.", err=True)
        sys.exit(1)

    # Destination directory
    if destination is None:
        destination = get_destination()

    try:
        destination = resolve_path_safely(destination, check_symlink=not allow_symlinks)
    except ValueError as error:
        sanitized_error = format_path_error(error)
        click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_error}", err=True)
        click.echo("Hint: If you trust this path, rerun with `--allow-symlinks`.", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.secho(
            f"Error: Destination directory not found: {sanitize_path_for_error(destination)}",
            fg="red",
            err=True,
        )
        click.echo("Hint: Set `--destination` or run `wslshot configure`.", err=True)
        sys.exit(1)

    # Output format
    if output_format is None:
        output_format = config["default_output_format"]

    if output_format.casefold() not in VALID_OUTPUT_FORMATS:
        click.secho(f"Error: Invalid `--output-style`: {output_format}", fg="red", err=True)
        valid_options = ", ".join(VALID_OUTPUT_FORMATS)
        suggestion = suggest_format(output_format, list(VALID_OUTPUT_FORMATS))
        hint = f"Hint: Use one of: {valid_options}."
        if suggestion:
            hint = f"{hint} {suggestion}"
        click.echo(hint, err=True)
        sys.exit(1)

    # Convert format
    if convert_to is None and config.get("default_convert_to"):
        convert_to = config["default_convert_to"]

    # If the user specified an image path, copy it to the destination directory.
    if image_path:
        try:
            # SECURITY: Validate image_path is not a symlink (PERSO-192 - critical 6th location)
            image_path_resolved = resolve_path_safely(image_path, check_symlink=not allow_symlinks)

            # SECURITY: Validate file content, not just extension (PERSO-193 - CWE-434)
            validate_image_file(image_path_resolved, max_size_bytes=max_file_size_bytes)
        except ValueError as error:
            sanitized_error = format_path_error(error)
            error_msg = str(error).casefold()
            if "symlink" in error_msg:
                click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_error}", err=True)
                if not allow_symlinks:
                    click.echo(
                        "Hint: If you trust this path, rerun with `--allow-symlinks`.",
                        err=True,
                    )
            else:
                click.secho(f"Error: {sanitized_error}", fg="red", err=True)

            click.echo(f"Source file: {sanitize_path_for_error(image_path)}", err=True)
            sys.exit(1)
        except FileNotFoundError:
            click.secho(
                f"Error: Image file not found: {sanitize_path_for_error(image_path)}",
                fg="red",
                err=True,
            )
            click.echo("Hint: Check the path and try again.", err=True)
            sys.exit(1)

        image_path = (image_path_resolved,)  # For compatibility with copy_screenshots()
        try:
            copied_screenshots = copy_screenshots(
                image_path,
                destination,
                max_file_size_bytes=max_file_size_bytes,
                max_total_size_bytes=max_total_size_bytes,
            )
        except ValueError as error:
            click.secho(f"Error: {error}", fg="red", err=True)
            sys.exit(1)
    else:
        # Copy the screenshot(s) to the destination directory.
        source_screenshots = get_screenshots(source, count, max_file_size_bytes=max_file_size_bytes)
        try:
            copied_screenshots = copy_screenshots(
                source_screenshots,
                destination,
                max_file_size_bytes=max_file_size_bytes,
                max_total_size_bytes=max_total_size_bytes,
            )
        except ValueError as error:
            click.secho(f"Error: {error}", fg="red", err=True)
            sys.exit(1)

    # Convert images if --convert-to option is provided
    if convert_to:
        converted_screenshots: tuple[Path, ...] = ()
        for screenshot in copied_screenshots:
            try:
                converted_path = convert_image_format(screenshot, convert_to)
                converted_screenshots += (converted_path,)
            except ValueError as error:
                sanitized_error = sanitize_error_message(str(error), (screenshot,))
                click.secho(f"Error: {sanitized_error}", fg="red", err=True)
                sys.exit(1)
        copied_screenshots = converted_screenshots

    relative_screenshots: tuple[Path, ...] = ()
    git_root: Path | None = None

    if is_git_repo():
        try:
            git_root = get_git_root()
        except RuntimeError as error:
            click.secho(f"Error: {error}", fg="red", err=True)
        else:
            relative_screenshots = format_screenshots_path_for_git(copied_screenshots, git_root)

            if bool(config["auto_stage_enabled"]) and relative_screenshots:
                stage_screenshots(relative_screenshots, git_root)

    if relative_screenshots:
        print_formatted_path(output_format, relative_screenshots, relative_to_repo=True)
    else:
        print_formatted_path(output_format, copied_screenshots, relative_to_repo=False)


def get_screenshots(
    source: str, count: int, max_file_size_bytes: int | None = None
) -> tuple[Path, ...]:
    """
    Get the most recent screenshot(s) from the source directory.

    Args:
    - source: The source directory.
    - count: The number of screenshots to fetch.
    - max_file_size_bytes: Per-file size cap in bytes (None uses default).

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
                if Path(entry.name).suffix.lower() in SUPPORTED_EXTENSIONS:
                    file_path = Path(entry.path)
                    try:
                        # Stat once and check if it's a regular file
                        stat_result = file_path.stat()
                        if S_ISREG(stat_result.st_mode):
                            # SECURITY: Validate file content, not just extension (PERSO-193 - CWE-434)
                            try:
                                validate_image_file(
                                    file_path,
                                    max_size_bytes=max_file_size_bytes,
                                    file_size=stat_result.st_size,
                                )
                                file_stats.append((file_path, stat_result.st_mtime))
                            except ValueError as e:
                                # Graceful degradation: skip invalid files with warning
                                click.echo(
                                    f"{WARNING_PREFIX} Skipping invalid image file: {e}",
                                    err=True,
                                )
                    except OSError:
                        # Skip files we can't stat (broken symlinks, permission issues, etc.)
                        pass

        # Use heapq for efficient partial sorting: O(N log count) instead of O(N log N)
        top_files = heapq.nlargest(count, file_stats, key=lambda x: x[1])
        screenshots = [file for file, _ in top_files]

        sanitized_source = sanitize_path_for_error(source)

        if len(screenshots) == 0:
            click.secho(
                f"Error: No screenshots found in {sanitized_source}",
                fg="red",
                err=True,
            )
            click.echo("Hint: Set `--source` or run `wslshot configure`.", err=True)
            sys.exit(1)

        if len(screenshots) < count:
            click.secho(
                f"Error: Only {len(screenshots)} screenshot(s) found in {sanitized_source}, "
                f"but you asked for {count}.",
                fg="red",
                err=True,
            )
            click.echo("Hint: Lower `--count` or check the source directory.", err=True)
            sys.exit(1)
    except OSError as error:
        sanitized_error = format_path_error(error)
        click.secho(f"Error: {sanitized_error}", fg="red", err=True)
        click.echo(f"Source directory: {sanitize_path_for_error(source)}", err=True)
        sys.exit(1)

    return tuple(screenshots)


def copy_screenshots(
    screenshots: tuple[Path, ...],
    destination: str,
    *,
    max_file_size_bytes: int | None = MAX_IMAGE_FILE_SIZE_BYTES,
    max_total_size_bytes: int | None = MAX_TOTAL_IMAGE_SIZE_BYTES,
) -> tuple[Path, ...]:
    """
    Copy the screenshot(s) to the destination directory
    and rename them with unique filesystem-friendly names.

    Args:
    - screenshots: A tuple of Path objects representing the screenshot(s) to copy.
    - destination: The path to the destination directory.
    - max_file_size_bytes: Per-file size cap (None uses default).
    - max_total_size_bytes: Aggregate size cap (None disables cap).

    Returns:
    - A tuple of Path objects representing the new locations of the copied screenshot(s).
    """
    copied_screenshots: tuple[Path, ...] = ()

    # SECURITY: Enforce aggregate size limit to prevent DoS (PERSO-193)
    total_size = 0
    total_limit = max_total_size_bytes
    per_file_limit = max_file_size_bytes

    for screenshot in screenshots:
        try:
            stat_result = screenshot.stat()
        except OSError as e:
            sanitized_error = sanitize_error_message(str(e), (screenshot,))
            click.echo(
                f"{WARNING_PREFIX} Cannot read file. Skipping: {sanitize_path_for_error(screenshot)} "
                f"({sanitized_error})",
                err=True,
            )
            continue

        # SECURITY: Defense-in-depth validation before copying (PERSO-193 - CWE-434)
        try:
            validate_image_file(
                screenshot,
                max_size_bytes=per_file_limit,
                file_size=stat_result.st_size,
            )

            # Check total size limit
            total_size += stat_result.st_size

            if total_limit is not None and total_size > total_limit:
                click.echo(
                    f"{WARNING_PREFIX} Total size limit reached "
                    f"({total_limit / 1024 / 1024:.0f}MB). Skipping remaining files.",
                    err=True,
                )
                break

        except ValueError as e:
            # Graceful degradation: skip invalid files with warning
            click.echo(
                f"{WARNING_PREFIX} Skipping invalid image file: {e}",
                err=True,
            )
            continue

        new_screenshot_name = generate_screenshot_name(screenshot)
        new_screenshot_path = Path(destination) / new_screenshot_name
        try:
            shutil.copy(screenshot, new_screenshot_path)
        except OSError as e:
            sanitized_error = sanitize_error_message(str(e), (screenshot, new_screenshot_path))
            raise ValueError(
                f"Could not copy {sanitize_path_for_error(screenshot)} "
                f"to {sanitize_path_for_error(new_screenshot_path)}: {sanitized_error}"
            ) from e
        copied_screenshots += (Path(destination) / new_screenshot_name,)

    return copied_screenshots


def generate_screenshot_name(screenshot_path: Path) -> str:
    """
    Produce a filesystem-friendly name for a copied screenshot.
    """
    suffix = screenshot_path.suffix.lower()
    unique_fragment = uuid.uuid4().hex

    return f"{unique_fragment}{suffix}"


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

    # Precompute destination path so it can be sanitized on failure
    new_path = source_path.with_suffix(f".{target_format}")

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
        sanitized_error = sanitize_error_message(str(e), (source_path, new_path))
        sanitized_path = sanitize_path_for_error(source_path)
        raise ValueError(f"Failed to convert image {sanitized_path}: {sanitized_error}") from e


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
        hinted = False
        for screenshot in screenshots:
            try:
                subprocess.run(
                    ["git", "add", str(screenshot)],
                    check=True,
                    cwd=git_root,
                )
            except subprocess.CalledProcessError as e:
                click.echo(f"{WARNING_PREFIX} Auto-staging failed for {screenshot}: {e}", err=True)
                if not hinted:
                    click.echo(
                        "Hint: Disable it with `wslshot configure --auto-stage-enabled false`, "
                        "or run `git add` yourself.",
                        err=True,
                    )
                    hinted = True


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
    normalized_output_format = output_format.casefold()
    for screenshot in screenshots:
        # Adding a '/' to the screenshot path if the destination is a Git repo.
        # This is because the screenshot path is relative to the git repo's.
        screenshot_path = f"/{screenshot}" if relative_to_repo else str(screenshot)

        if normalized_output_format == OUTPUT_FORMAT_MARKDOWN:
            click.echo(f"![{screenshot.name}]({screenshot_path})")

        elif normalized_output_format == OUTPUT_FORMAT_HTML:
            click.echo(f'<img src="{screenshot_path}" alt="{screenshot.name}">')

        elif normalized_output_format == OUTPUT_FORMAT_TEXT:
            click.echo(screenshot_path)

        else:
            valid_options = ", ".join(VALID_OUTPUT_FORMATS)
            click.echo(f"Error: Invalid `--output-style`: {output_format}", err=True)
            click.echo(f"Hint: Use one of: {valid_options}.", err=True)
            sys.exit(1)


def get_config_file_path(*, create_if_missing: bool = True) -> Path:
    """
    Get the configuration file path, optionally creating the file.
    """
    config_file_path = Path.home() / ".config" / "wslshot" / "config.json"

    if config_file_path.is_symlink():
        raise SecurityError("Config file is a symlink; refusing to use it.")

    if create_if_missing:
        create_directory_safely(config_file_path.parent, mode=CONFIG_DIR_PERMISSIONS)

        if not config_file_path.exists():
            # Write default config without interactive prompts
            write_config_safely(config_file_path, DEFAULT_CONFIG.copy())

    return config_file_path


def get_config_file_path_or_exit(*, create_if_missing: bool = True) -> Path:
    """Return config path or exit with a user-friendly security error."""
    try:
        return get_config_file_path(create_if_missing=create_if_missing)
    except SecurityError as error:
        click.echo(f"{SECURITY_ERROR_PREFIX} {error}", err=True)
        error_msg = str(error).lower()
        if "symlink" in error_msg:
            click.echo("Hint: Remove the symlink and rerun `wslshot configure`.", err=True)
        elif "different user" in error_msg:
            click.echo("Hint: Check directory ownership or use a different path.", err=True)
        sys.exit(1)


def read_config(config_file_path: Path) -> dict[str, object]:
    """
    Read the configuration file.

    This function expects `config_file_path` to exist. Use `get_config_file_path()` when you
    want to create a default config file if missing.

    Args:
        config_file_path: The path to the configuration file.

    Returns:
        The configuration file as a dictionary.
    """
    try:
        with open(config_file_path, "r", encoding="UTF-8") as file:
            config = json.load(file)

    except json.JSONDecodeError as error:
        if _is_interactive_terminal():
            click.echo(
                f"{WARNING_PREFIX} Config file {sanitize_path_for_error(config_file_path)} is corrupted ({error}). "
                "We'll recreate it interactively.",
                err=True,
            )
            _backup_corrupted_file_or_warn(config_file_path)
            write_config(config_file_path)
            with open(config_file_path, "r", encoding="UTF-8") as file:
                config = json.load(file)
            return config

        click.echo(
            f"{WARNING_PREFIX} Config file {sanitize_path_for_error(config_file_path)} is corrupted ({error}). "
            "Resetting to defaults.",
            err=True,
        )
        click.echo("Hint: Run `wslshot configure` to set your preferences.", err=True)

        _backup_corrupted_file_or_warn(config_file_path)

        create_directory_safely(config_file_path.parent, mode=CONFIG_DIR_PERMISSIONS)
        config = DEFAULT_CONFIG.copy()
        write_config_or_exit(config_file_path, config)

    return config


def migrate_config(config_path: Path, *, dry_run: bool = False) -> dict[str, object]:
    """
    Migrate legacy config values to current format.

    Migrations performed:
    - `plain_text` becomes `text` in `default_output_format`

    Args:
        config_path: Path to config file
        dry_run: If True, return changes without writing

    Returns:
        Dictionary with migration report:
        {
            "migrated": bool,
            "changes": list[str],
            "config": dict
        }
    """
    try:
        with open(config_path, "r", encoding="UTF-8") as f:
            config = json.load(f)
    except FileNotFoundError as e:
        sanitized_error = format_path_error(e)
        return {
            "migrated": False,
            "changes": [],
            "error": f"Cannot read config file: {sanitized_error}",
            "config": {},
        }
    except json.JSONDecodeError as e:
        return {
            "migrated": False,
            "changes": [],
            "error": f"Cannot read config file: {e}",
            "config": {},
        }

    # Validate config is a dictionary
    if not isinstance(config, dict):
        return {
            "migrated": False,
            "changes": [],
            "error": f"Invalid config format: expected an object, got {type(config).__name__}",
            "config": {},
        }

    changes = []

    # Migration: plain_text becomes text
    default_output_format = config.get("default_output_format")
    if (
        isinstance(default_output_format, str)
        and default_output_format.casefold() == LEGACY_OUTPUT_FORMAT_PLAIN_TEXT
    ):
        config["default_output_format"] = OUTPUT_FORMAT_TEXT
        changes.append("default_output_format: 'plain_text' becomes 'text'")

    # Write migrated config
    if changes and not dry_run:
        try:
            write_config_safely(config_path, config)
        except (OSError, SecurityError) as e:
            sanitized_error = sanitize_error_message(str(e), (config_path,))
            return {
                "migrated": False,
                "changes": changes,
                "error": f"Cannot write config file: {sanitized_error}",
                "config": config,
            }

    return {
        "migrated": bool(changes) and not dry_run,
        "changes": changes,
        "config": config,
    }


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
        click.secho("Updating config file...", fg="yellow")
    else:
        click.secho("Creating config file...", fg="yellow")
    click.echo()

    # Prompt the user for configuration values.
    config: dict[str, object] = {}
    for field, spec in CONFIG_FIELD_SPECS.items():
        message = spec.prompt
        default = spec.default

        if field in ("default_source", "default_destination"):
            value = get_validated_directory_input(field, message, current_config, default)
            config[field] = spec.normalize(value)
            continue

        if field == "auto_stage_enabled":
            value = get_config_boolean_input(field, message, current_config, default)
            config[field] = spec.normalize(value)
            continue

        if field == "default_output_format":
            value = get_validated_input(
                field,
                message,
                current_config,
                default,
                options=list(VALID_OUTPUT_FORMATS),
            )
            config[field] = spec.normalize(value)
            continue

        if field == "default_convert_to":
            while True:
                value = get_config_input(field, message, current_config, default or "")
                try:
                    config[field] = spec.normalize(value)
                except ValueError as error:
                    click.secho(f"Error: {error}", fg="red", err=True)
                    click.echo()
                    continue
                break
            continue

        if field in ("max_file_size_mb", "max_total_size_mb"):
            value = get_config_input(field, message, current_config, default)
            try:
                config[field] = spec.normalize(value)
            except (TypeError, ValueError):
                config[field] = default
            continue

        value = get_config_input(field, message, current_config, default)
        config[field] = spec.normalize(value)

    # Writing configuration to file
    write_config_or_exit(config_file_path, config)

    if current_config:
        click.secho("Configuration saved.", fg="green")
    else:
        click.secho("Configuration file created.", fg="green")


def get_config_input(field, message, current_config, default="") -> str:
    existing = current_config.get(field, default)
    if existing is None:
        existing = default
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
            sanitized_msg = format_path_error(error)
            click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_msg}", err=True)
        except FileNotFoundError as error:
            sanitized_msg = format_path_error(error)
            click.secho(
                f"Error: Invalid {field.replace('_', ' ')}: {sanitized_msg}",
                fg="red",
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
            click.secho(
                f"Error: Invalid value for {field.replace('_', ' ')}. "
                f"Use one of: {', '.join(options)}.",
                fg="red",
                err=True,
            )
            continue

        return value


def _write_config_field(field: str, normalized_value: object) -> None:
    """
    Persist a single, already-normalized config field value.

    This helper centralizes the read, update, and write sequence for setter functions that
    perform their own validation and normalization.
    """
    config_file_path = get_config_file_path_or_exit()
    config = read_config(config_file_path)
    config[field] = normalized_value

    write_config_or_exit(config_file_path, config)


def update_config_field(field: str, value: object) -> None:
    """
    Update a single config field.

    Args:
        field: Config key to update
        value: New value for the field

    Raises:
        click.ClickException: If `field` is not a valid config key or `value` is invalid
    """
    spec = CONFIG_FIELD_SPECS.get(field)
    if spec is None:
        raise click.ClickException(f"Unknown config field: {field}")

    try:
        normalized_value = spec.normalize(value)
    except (ValueError, TypeError, FileNotFoundError) as error:
        sanitized = format_path_error(error)
        raise click.ClickException(
            f"Invalid value for {field}: {sanitized}\n"
            "Hint: See `wslshot configure --help` for valid values."
        ) from error

    _write_config_field(field, normalized_value)


def set_default_source(source_str: str) -> None:
    """
    Set the default source directory.

    Args:
        source_str: The default source directory.
    """
    if not source_str.strip():
        source = ""
    else:
        try:
            source = str(resolve_path_safely(source_str))
        except ValueError as error:
            sanitized_msg = format_path_error(error)
            click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_msg}", err=True)
            sys.exit(1)
        except FileNotFoundError as error:
            sanitized_msg = format_path_error(error)
            click.secho(f"Error: Invalid source directory: {sanitized_msg}", fg="red", err=True)
            sys.exit(1)

    _write_config_field("default_source", source)


def set_default_destination(destination_str: str) -> None:
    """
    Set the default destination directory.

    Args:
        destination_str: The default destination directory.
    """
    if not destination_str.strip():
        destination = ""
    else:
        try:
            destination = str(resolve_path_safely(destination_str))
        except ValueError as error:
            sanitized_msg = format_path_error(error)
            click.echo(f"{SECURITY_ERROR_PREFIX} {sanitized_msg}", err=True)
            sys.exit(1)
        except FileNotFoundError as error:
            sanitized_msg = format_path_error(error)
            click.secho(
                f"Error: Invalid destination directory: {sanitized_msg}",
                fg="red",
                err=True,
            )
            sys.exit(1)

    _write_config_field("default_destination", destination)


def get_destination() -> Path:
    """
    Get the destination directory.

    Returns:
        The destination directory.
    """
    if is_git_repo():
        return get_git_repo_img_destination()

    config = read_config(get_config_file_path_or_exit())
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
        raise RuntimeError("Could not determine the Git repository root.") from error

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
        click.secho(f"Error: {error}", fg="red", err=True)
        sys.exit(1)

    for relative_parts in GIT_IMAGE_DIRECTORY_PRIORITY:
        candidate = git_root.joinpath(*relative_parts)
        if candidate.exists():
            return candidate

    destination = git_root.joinpath(*GIT_IMAGE_DIRECTORY_PRIORITY[-1])
    try:
        # Skip permission hardening for git-tracked directories since they may
        # be intentionally group-writable in shared repositories (umask 0002)
        create_directory_safely(destination, mode=0o755, harden_permissions=False)
    except SecurityError as error:
        click.echo(f"{SECURITY_ERROR_PREFIX} {error}", err=True)
        error_msg = str(error).lower()
        if "symlink" in error_msg:
            click.echo("Hint: Remove the symlink and try again.", err=True)
        elif "different user" in error_msg:
            click.echo("Hint: Check directory ownership or use a different path.", err=True)
        sys.exit(1)
    return destination


def set_auto_stage(auto_stage_enabled: bool) -> None:
    """
    Set whether screenshots are automatically staged when copied to a Git repository.

    Args:
        auto_stage_enabled: Whether screenshots are automatically staged when copied to a Git repo.
    """
    update_config_field("auto_stage_enabled", auto_stage_enabled)


def set_default_output_format(output_format: str) -> None:
    """
    Set the default output format.

    Args:
        output_format: The default output format.
    """
    if output_format.casefold() not in VALID_OUTPUT_FORMATS:
        click.secho(f"Error: Invalid `--output-style`: {output_format}", fg="red", err=True)
        valid_options = ", ".join(VALID_OUTPUT_FORMATS)
        suggestion = suggest_format(output_format, list(VALID_OUTPUT_FORMATS))
        hint = f"Hint: Use one of: {valid_options}."
        if suggestion:
            hint = f"{hint} {suggestion}"
        click.echo(hint, err=True)
        sys.exit(1)

    _write_config_field("default_output_format", output_format.casefold())


def set_default_convert_to(convert_format: str | None) -> None:
    """
    Set the default image conversion format.

    Args:
        convert_format: The default conversion format (png, jpg/jpeg, webp, gif, or None).
    """
    try:
        normalized_convert_format = normalize_default_convert_to(convert_format)
    except (TypeError, ValueError) as error:
        click.secho(f"Error: {error}", fg="red", err=True)
        sys.exit(1)

    _write_config_field("default_convert_to", normalized_convert_format)


@wslshot.command()
@click.option("--source", "-s", help="Default source directory used by `wslshot fetch`.")
@click.option(
    "--destination",
    "-d",
    help="Default destination directory used by `wslshot fetch`.",
)
@click.option(
    "--auto-stage-enabled",
    type=bool,
    help="Automatically run `git add` on copied screenshots when in a Git repo.",
)
@click.option(
    "--output-style",
    "output_format",
    help=f"Default output style for printed paths ({OUTPUT_FORMATS_HELP}).",
)
@click.option(
    "--convert-to",
    "-c",
    type=click.Choice(list(VALID_CONVERT_FORMATS), case_sensitive=False),
    help="Default format to convert to after copying (png, jpg/jpeg, webp, gif).",
)
def configure(source, destination, auto_stage_enabled, output_format, convert_to):
    """
    Set defaults for `wslshot fetch` (paths, output style, conversion, and Git auto-staging).

    Run with no options to configure interactively.

    \b
    Examples:
      wslshot configure
      wslshot configure --source "<...>/Screenshots"
      wslshot configure --destination "<...>/img"
      wslshot configure --output-style text
    """
    # When no options are specified, ask the user for their preferences.
    if all(x is None for x in (source, destination, auto_stage_enabled, output_format, convert_to)):
        write_config(get_config_file_path_or_exit())

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


@wslshot.command(name="migrate-config")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would change without writing.",
)
def migrate_config_cmd(dry_run):
    """
    Migrate older config values to the current names (for example, `plain_text` to `text`).

    \b
    Examples:
      wslshot migrate-config --dry-run
      wslshot migrate-config
    """
    config_path = get_config_file_path_or_exit(create_if_missing=False)

    if not config_path.exists():
        click.secho("Nothing to migrate: config file not found.", fg="yellow", err=True)
        click.echo("Hint: Create one with `wslshot configure`.", err=True)
        sys.exit(0)

    click.echo(f"Config file: {sanitize_path_for_error(config_path)}")
    click.echo()

    result = migrate_config(config_path, dry_run=dry_run)

    if "error" in result:
        click.secho(f"Error: {result['error']}", fg="red", err=True)
        sys.exit(1)

    if not result["changes"]:
        click.secho("Config is up to date. No migration needed.", fg="green")
        sys.exit(0)

    # Show changes
    if dry_run:
        click.secho("Would change:", fg="yellow")
    else:
        click.secho("Changed:", fg="green")

    for change in result["changes"]:
        click.echo(f"  - {change}")

    if dry_run:
        click.echo()
        click.echo("Hint: Re-run without `--dry-run` to apply these changes.")
    else:
        click.echo()
        click.secho("Migration complete.", fg="green")
