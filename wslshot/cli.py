"""
WSLShot CLI.

This command-line interface allows for efficient management of screenshots
on a Linux VM with Windows as the host OS.

Features:

- Fetch and copy the most recent screenshots using the 'wslshot' command.
- Specify the number of screenshots to be processed with the '--count' option.
- Customize the source directory using '--source'.
- Customize the destination directory using '--destination'.
- Choose your preferred output format (Markdown, HTML, or plain text) with the '--output-format' option.
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
from pathlib import Path
from typing import Any

import click
from click_default_group import DefaultGroup


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

        # Set permissions on temp file
        os.chmod(temp_path, mode)

        # Atomic rename (POSIX guarantees atomicity)
        os.replace(temp_path, str(path))

    except Exception:
        # Cleanup temp file on any error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


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
    - Customize output format (Markdown, HTML, or plain text) with --output-format.
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
    "output_format_new",
    help=("Specify the output style (markdown, html, text). Overrides the default set in config."),
)
@click.option(
    "--output-format",
    "-f",
    "output_format_deprecated",
    help=(
        "[DEPRECATED - use --output-style] "
        "Specify the output format (markdown, html, text). Overrides the default set in config."
    ),
)
@click.argument("image_path", type=click.Path(exists=True), required=False)
def fetch(source, destination, count, output_format_new, output_format_deprecated, image_path):
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
        source = Path(source).resolve(strict=True)
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
        destination = Path(destination).resolve(strict=True)
    except FileNotFoundError:
        click.echo(
            f"{click.style(f'Destination directory {destination} does not exist.', fg='red')}",
            err=True,
        )
        sys.exit(1)

    # Handle deprecated --output-format option
    output_format = output_format_new or output_format_deprecated

    if output_format_deprecated is not None:
        warnings.warn(
            "The --output-format/-f option is deprecated and will be removed in v1.0.0. "
            "Use --output-style instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Output format
    if output_format is None:
        output_format = config["default_output_format"]

    # Emit deprecation warning for plain_text
    if output_format.casefold() == "plain_text":
        warnings.warn(
            "The 'plain_text' output format is deprecated and will be removed in v1.0.0. "
            "Use 'text' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        output_format = "text"  # Normalize to new name

    if output_format.casefold() not in ("markdown", "html", "text", "plain_text"):
        click.echo(f"Invalid output format: {output_format}", err=True)
        click.echo("Valid options are: markdown, html, text", err=True)
        suggestion = suggest_format(output_format, ["markdown", "html", "text"])
        if suggestion:
            click.echo(suggestion, err=True)
        sys.exit(1)

    # If the user specified an image path, copy it to the destination directory.
    if image_path:
        try:
            if not image_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                raise ValueError("Invalid image format (supported formats: png, jpg, jpeg, gif).")
        except ValueError as error:
            click.echo(
                f"{click.style('An error occurred while fetching the screenshot(s).', fg='red')}",
                err=True,
            )
            click.echo(f"{error}", err=True)
            click.echo(f"Source file: {image_path}", err=True)
            sys.exit(1)

        image_path = (Path(image_path),)  # For compatibility with copy_screenshots()
        copied_screenshots = copy_screenshots(image_path, destination)
    else:
        # Copy the screenshot(s) to the destination directory.
        source_screenshots = get_screenshots(source, count)
        copied_screenshots = copy_screenshots(source_screenshots, destination)

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
        # Collect files with different extensions
        extensions = ("png", "jpg", "jpeg", "gif")
        screenshots = [file for ext in extensions for file in Path(source).glob(f"*.{ext}")]

        # Cache stat results and use heapq for efficient partial sorting
        # O(N log count) instead of O(N log N) full sort
        file_stats = [(file, file.stat().st_mtime) for file in screenshots]
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
        # Batch all files into a single git add command
        subprocess.run(
            ["git", "add"] + [str(screenshot) for screenshot in screenshots],
            check=True,
            cwd=git_root,
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"Failed to stage screenshots: {e}", err=True)


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

        elif output_format.casefold() in ("plain_text", "text"):
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
            "default_output_format": "markdown"
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
                options=["markdown", "html", "text", "plain_text"],
            )
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
            return str(Path(directory).resolve(strict=True))
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
        source: str = str(Path(source_str).resolve(strict=True))
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
        destination: str = str(Path(destination_str).resolve(strict=True))
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
    if output_format.casefold() not in ["markdown", "html", "text", "plain_text"]:
        click.echo(click.style(f"Invalid output format: {output_format}", fg="red"), err=True)
        click.echo("Valid options are: markdown, html, text", err=True)
        suggestion = suggest_format(output_format, ["markdown", "html", "text"])
        if suggestion:
            click.echo(click.style(suggestion, fg="yellow"), err=True)
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    # Normalize plain_text to text when storing
    normalized_format = output_format.casefold().replace("plain_text", "text")
    config["default_output_format"] = normalized_format

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
    "--output-format",
    "-f",
    help="Set the default output format (markdown, HTML, text).",
)
def configure(source, destination, auto_stage_enabled, output_format):
    """
    Set the default source directory, control automatic staging, and set the default output format.

    Usage:

    - Specify the default source directory with --source.

    - Control whether screenshots are automatically staged with --auto-stage.

    - Set the default output format (markdown, HTML, text) with --output-format.

    ___

    The source directory must be a shared folder between Windows and your Linux VM:

    - If you are using WSL, you can choose the 'Screenshots' folder in your 'Pictures' directory. (e.g., /mnt/c/users/...)

    - For VM users, you should configure a shared folder between Windows and the VM before proceeding.
    """
    # When no options are specified, ask the user for their preferences.
    if all(x is None for x in (source, destination, auto_stage_enabled, output_format)):
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
