"""
WSLShot CLI.

This command-line interface allows for efficient management of screenshots
on a Linux VM with Windows as the host OS.

Features:

- Fetch and copy the most recent screenshots using the 'wslshot' command.
- Specify the number of screenshots to be processed with the '--count' option.
- Customize the source directory using '--source'.
- Customize the destination directory using '--destination'.
- Choose your preferred output format (Markdown, HTML, or raw path) with the '--output' option.
- Configure default settings with the 'configure' subcommand.

For detailed usage instructions, use 'wslshot --help' or 'wslshot [command] --help'.
"""


import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import click
from click_default_group import DefaultGroup


@click.group(cls=DefaultGroup, default="fetch", default_if_no_args=True)
@click.version_option(package_name="wslshot")
def wslshot():
    """
    Fetches and copies the latest screenshot(s) from the source to the specified destination.

    Usage:

    - Customize the number of screenshots with --count.
    - Specify source and destination directories with --source and --destination.
    - Customize output format (Markdown, HTML, or path) with --output.
    """


@wslshot.command()
@click.option(
    "--source", "-s", help="Specify a custom source directory for this operation."
)
@click.option(
    "--destination",
    "-d",
    help="Specify a custom destination directory for this operation.",
)
@click.option(
    "--count",
    "-n",
    default=1,
    help="Specify the number of most recent screenshots to fetch. Defaults to 1.",
)
@click.option(
    "--output-format",
    "-f",
    help=(
        "Specify the output format (markdown, HTML, path). Overrides the default set in"
        " config."
    ),
)
@click.argument("image_path", type=click.Path(exists=True), required=False)
def fetch(source, destination, count, output_format, image_path):
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
        print(f"Source directory '{source}' does not exist.")
        sys.exit(1)

    # Destination directory
    if destination is None:
        destination = get_destination()

    try:
        destination = Path(destination).resolve(strict=True)
    except FileNotFoundError:
        print(f"Destination directory '{destination}' does not exist.")
        sys.exit(1)

    # Output format
    if output_format is None:
        output_format = config["default_output_format"]

    if output_format.casefold() not in ("markdown", "html", "plain_text"):
        print(f"Invalid output format: {output_format}")
        print("Valid options are: markdown, html, plain_text")
        sys.exit(1)

    # If the user specified an image path, copy it to the destination directory.
    if image_path:
        try:
            if not image_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                raise ValueError(
                    "Invalid image format (supported formats: png, jpg, jpeg, gif)."
                )
        except ValueError as error:
            click.echo(
                f"{click.style('An error occurred while fetching the screenshot(s).',fg='red')}",
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

    # Automatically stage the screenshot(s) if the destination is a Git repo.
    # But only if auto_stage is enabled in the config.
    if is_git_repo():
        copied_screenshots = format_screenshots_path_for_git(copied_screenshots)
        if bool(config["auto_stage_enabled"]):
            stage_screenshots(copied_screenshots)

    # Print the screenshot(s)'s path in the specified format.
    print_formatted_path(output_format, copied_screenshots)


def get_screenshots(source: str, count: int) -> Tuple[Path, ...]:
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
        screenshots = [
            file for ext in extensions for file in Path(source).glob(f"*.{ext}")
        ]

        # Sort by modification time
        screenshots.sort(key=lambda file: file.stat().st_mtime, reverse=True)

        # Take the `count` most recent files
        screenshots = screenshots[:count]

        if len(screenshots) == 0:
            raise ValueError("No screenshot found.")

        if len(screenshots) < count:
            raise ValueError(
                f"You requested {count} screenshot(s), but only {len(screenshots)} were found."
            )
    except ValueError as error:
        click.echo(
            f"{click.style('An error occurred while fetching the screenshot(s).',fg='red')}",
            err=True,
        )
        click.echo(f"{error}", err=True)
        click.echo(f"Source directory: {source}\n", err=True)
        sys.exit(1)

    return tuple(screenshots)


def copy_screenshots(
    screenshots: Tuple[Path, ...], destination: str
) -> Tuple[Path, ...]:
    """
    Copy the screenshot(s) to the destination directory,
    and rename the screenshot(s) to the current date and time.

    Args:
    - screenshots: A tuple of Path objects representing the screenshot(s) to copy.
    - destination: The path to the destination directory.

    Returns:
    - A tuple of Path objects representing the new locations of the copied screenshot(s).
    """
    copied_screenshots: Tuple[Path, ...] = ()

    for idx, screenshot in enumerate(screenshots):
        new_screenshot_name = rename_screenshot(idx, screenshot)
        new_screenshot_path = Path(destination) / new_screenshot_name
        shutil.copy(screenshot, new_screenshot_path)
        copied_screenshots += (Path(destination) / new_screenshot_name,)

    return copied_screenshots


def rename_screenshot(idx: int, screenshot_path: Path) -> str:
    """
    Rename the screenshot to the current date and time.

    Returns:
    - The new screenshot name.
    """
    original_name = screenshot_path.stem
    file_extension = screenshot_path.suffix.lstrip(".")

    # Check if the file is a GIF.
    is_gif = file_extension == "gif"
    prefix = "animated_" if is_gif else ""

    if is_gif:
        return f"{prefix}{original_name}.{file_extension}"
    else:
        # Rename screenshot with ISO 8601 date and time, and append the index.
        return f"{prefix}screenshot_{datetime.datetime.now().isoformat(timespec='seconds')}_{idx}.{file_extension}"


def stage_screenshots(screenshots: Tuple[Path]) -> None:
    """
    Automatically stage the screenshot(s) if the destination is a Git repo.

    Args:

    - screenshots: The screenshot(s).
    """
    # Automatically stage the screenshot(s) if the destination is a Git repo.
    for screenshot in screenshots:
        try:
            subprocess.run(["git", "add", str(screenshot)], check=True)
        except subprocess.CalledProcessError:
            click.echo(f"Failed to stage screenshot '{screenshot}'.")


def format_screenshots_path_for_git(screenshots: Tuple[Path]) -> Tuple[Path, ...]:
    """
    Format the screenshot(s)'s path for git.

    Args:

    - screenshots: The screenshot(s).
    """
    img_dir = get_git_repo_img_destination().parent.parent
    formatted_screenshots: Tuple[Path, ...] = ()

    for screenshot in screenshots:
        formatted_screenshots += (Path(screenshot).relative_to(img_dir),)

    return formatted_screenshots


def print_formatted_path(output_format: str, screenshots: Tuple[Path]) -> None:
    """
    Print the screenshot(s)'s path in the specified format.

    Args:

    - output_format: The output format.
    - screenshots: The screenshot(s).
    """
    for screenshot in screenshots:
        # Adding a '/' to the screenshot path if the destination is a Git repo.
        # This is because the screenshot path is relative to the git repo's.
        if is_git_repo():
            screenshot_path = f"/{screenshot}"
        else:
            screenshot_path = str(screenshot)  # This is an absolute path.

        if output_format == "markdown":
            print(f"![{screenshot.name}]({screenshot_path})")

        elif output_format == "html":
            print(f'<img src="{screenshot_path}" alt="{screenshot.name}">')

        elif output_format == "plain_text":
            print(screenshot_path)

        else:
            print(f"Invalid output format: {output_format}")
            sys.exit(1)


def get_config_file_path() -> Path:
    """
    Create the configuration file.
    """
    config_file_path = Path.home() / ".config" / "wslshot" / "config.json"
    config_file_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_file_path.exists():
        config_file_path.touch()
        write_config(config_file_path)

    return config_file_path


def read_config(config_file_path: Path) -> Dict[str, Any]:
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
            "Enter the default output format (markdown, html, plain_text)",
            "markdown",
        ),
    }

    # Prompt the user for configuration values.
    config = {}
    for field, (message, default) in config_fields.items():
        if field in ["default_source", "default_destination"]:
            config[field] = get_validated_directory_input(
                field, message, current_config, default
            )
        elif field == "auto_stage_enabled":
            config[field] = get_config_boolean_input(
                field, message, current_config, default
            )
        elif field == "default_output_format":
            config[field] = get_validated_input(
                field,
                message,
                current_config,
                default,
                options=["markdown", "html", "plain_text"],
            )
        else:
            config[field] = get_config_input(field, message, current_config, default)

    # Writing configuration to file
    try:
        with open(config_file_path, "w", encoding="UTF-8") as file:
            json.dump(config, file, indent=4)
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


def get_validated_input(
    field, message, current_config, default="", options=None
) -> str:
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
        source: Path = str(Path(source_str).resolve(strict=True))
    except FileNotFoundError as error:
        click.echo(
            click.style(f"Invalid source directory: {error}", fg="red"), err=True
        )
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_source"] = source

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file, indent=4)


def set_default_destination(destination_str: str) -> None:
    """
    Set the default destination directory.

    Args:
        destination: The default destination directory.
    """
    try:
        destination: Path = str(Path(destination_str).resolve(strict=True))
    except FileNotFoundError as error:
        click.echo(
            click.style(f"Invalid destination directory: {error}", fg="red"), err=True
        )
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_destination"] = destination

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file, indent=4)


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


def get_git_repo_img_destination() -> Path:
    """
    Get the destination directory for a Git repository.

    Returns:
        The destination directory for a Git repository.
    """
    try:
        git_root_str = (
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                check=True,
                stdout=subprocess.PIPE,
            )
            .stdout.strip()
            .decode("utf-8")
        )
    except subprocess.CalledProcessError:
        sys.exit("Failed to get git root directory.")

    git_root: Path = Path(git_root_str)

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

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file, indent=4)


def set_default_output_format(output_format: str) -> None:
    """
    Set the default output format.

    Args:
        output_format: The default output format.
    """
    if output_format.casefold() not in ["markdown", "html", "plain_text"]:
        click.echo(
            click.style(f"Invalid output format: {output_format}", fg="red"), err=True
        )
        click.echo("Valid options are: markdown, html, plain_text", err=True)
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_output_format"] = output_format.casefold()

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file, indent=4)


@wslshot.command()
@click.option(
    "--source", "-s", help="Specify the default source directory for this operation."
)
@click.option(
    "--destination",
    "-d",
    help="Specify the default destination directory for this operation.",
)
@click.option(
    "--auto-stage-enabled",
    type=bool,
    help=(
        "Control whether screenshots are automatically staged when copied to a git"
        " repository."
    ),
)
@click.option(
    "--output-format",
    "-f",
    help="Set the default output format (markdown, HTML, plain_text).",
)
def configure(source, destination, auto_stage_enabled, output_format):
    """
    Set the default source directory, control automatic staging, and set the default output format.

    Usage:

    - Specify the default source directory with --source.

    - Control whether screenshots are automatically staged with --auto-stage.

    - Set the default output format (markdown, HTML, path) with --output-format.

    ___

    The source directory must be a shared folder between Windows and your Linux VM:

    - If you are using WSL, you can choose the 'Screenshots' folder in your 'Pictures' directory. (e.g., /mnt/c/users/...)

    - For VM users, you should configure a shared folder between Windows and the VM before proceeding.
    """
    # When no options are specified, ask the user for their preferences.
    if not any((source, destination, auto_stage_enabled, output_format)):
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
