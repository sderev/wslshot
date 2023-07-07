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
- Configure default settings with the 'config' subcommand.

For detailed usage instructions, use 'wslshot --help' or 'wslshot [command] --help'.
"""


import datetime
import json
import os
import shutil
import subprocess
import sys
from typing import Tuple
from pathlib import Path

import click


@click.group(invoke_without_command=True, no_args_is_help=False)
@click.pass_context
@click.version_option()
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
def wslshot(ctx, source, destination, count, output_format):
    """
    Fetches and copies the latest screenshot(s) from the source to a specified destination.

    Usage:

    - Customize the number of screenshots with --count.
    - Specify source and destination directories with --source and --destination.
    - Customize output format (Markdown, HTML, or path) with --output.
    """
    if ctx.invoked_subcommand is None:
        wslshot_cli(source, destination, count, output_format)


def wslshot_cli(source, destination, count, output_format):
    """
    Fetches and copies the latest screenshot(s) from the source to a specified destination.

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
        print("Valid options are: markdown, HTML, plain_text")
        sys.exit(1)

    # Copy the screenshot(s) to the destination directory.
    source_screenshots = get_screenshots(source, count)
    copied_screenshots = copy_screenshots(source_screenshots, destination)

    # Automatically stage the screenshot(s) if the destination is a git repo.
    if is_git_repo():
        stage_screenshots(copied_screenshots)
        copied_screenshots = format_screenshots_path_for_git(copied_screenshots)

    # Print the screenshot(s)'s path in the specified format.
    print_formatted_path(output_format, copied_screenshots)


def get_screenshots(source: str, count: int) -> Tuple[Path]:
    """
    Get the most recent screenshot(s) from the source directory.

    Args:

    - source: The source directory.
    - count: The number of screenshots to fetch.

    Returns:

    - The screenshot(s)'s path.
    """
    # Get the most recent screenshot(s) from the source directory.
    screenshots = sorted(
        Path(source).glob("*.png"), key=os.path.getmtime, reverse=True
    )[:count]

    if len(screenshots) == 0:
        click.echo(f"No screenshots found in the source directory: {source}.")
        sys.exit(1)

    if len(screenshots) < count:
        raise ValueError(
            f"Only {len(screenshots)} screenshot(s) found in the source directory:"
            f" {source}."
        )

    return tuple(screenshots)


def copy_screenshots(screenshots: Tuple[Path], destination: str) -> Tuple[Path]:
    """
    Copy the screenshot(s) to the destination directory.

    Args:

    - source: The source directory.
    - destination: The destination directory.
    - count: The number of screenshots to fetch.
    """
    copied_screenshots = ()

    print(screenshots)
    for idx, screenshot in enumerate(screenshots):
        new_screenshot_name = rename_screenshot(idx)
        new_screenshot_path = Path(destination) / new_screenshot_name
        shutil.copy(screenshot, new_screenshot_path)
        copied_screenshots += (Path(destination) / new_screenshot_name,)

    return copied_screenshots


def rename_screenshot(idx) -> str:
    """
    Rename the screenshot to the current date and time.

    Returns:

    - The new screenshot name.
    """
    return (
        f"screenshot_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{idx}.png"
    )


def stage_screenshots(screenshots: Tuple[Path]) -> None:
    """
    Automatically stage the screenshot(s) if the destination is a git repo.

    Args:

    - screenshots: The screenshot(s).
    """
    # Automatically stage the screenshot(s) if the destination is a git repo.
    for screenshot in screenshots:
        try:
            subprocess.run(["git", "add", str(screenshot)], check=True)
        except subprocess.CalledProcessError:
            print(f"Failed to stage screenshot '{screenshot}'.")


def format_screenshots_path_for_git(screenshots: Tuple[Path]) -> Tuple[Path]:
    """
    Format the screenshot(s)'s path for git.

    Args:

    - screenshots: The screenshot(s).
    """
    img_dir = get_git_repo_img_destination().parent.parent
    formatted_screenshots = ()

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
        rel_screenshot = f"/{screenshot}"

        if output_format == "markdown":
            print(f"![{screenshot.name}]({rel_screenshot})")

        elif output_format == "html":
            print(f'<img src="{rel_screenshot}" alt="{screenshot.name}">')

        elif output_format == "plain_text":
            print(rel_screenshot)

        else:
            print(f"Invalid output format: {output_format}")
            sys.exit(1)


def get_config_file_path() -> Path:
    """
    Create the config file.
    """
    config_file_path = Path.home() / ".config" / "wslshot" / "config.json"
    config_file_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_file_path.exists():
        config_file_path.touch()
        write_default_config(config_file_path)

    return config_file_path


def write_default_config(config_file_path: Path) -> None:
    """
    Write the config file.

    Args:
        config_file_path: The path to the config file.
    """
    click.echo(f"{click.style('Creating the configuration file...', fg='yellow')}")

    # Ask the user for the source dir
    while True:
        try:
            click.echo(
                "The source directory must be a shared folder between Windows and your"
                " Linux VM."
            )

            click.echo()
            click.echo("---")

            click.echo(
                "* If you are using WSL, you can choose the 'Screenshots' folder in"
                " your 'Pictures' directory. (e.g., /mnt/c/users/...)"
            )

            click.echo()

            click.echo(
                "* For VM users, you should configure a shared folder between Windows"
                " and the VM before proceeding."
            )
            click.echo("---")
            click.echo()

            source = click.prompt(
                (
                    f"{click.style('Please enter the path for the default source directory', fg='blue')}"
                ),
                type=str,
            )
        except click.exceptions.Abort:
            click.echo(f"\n{click.style('Aborted', fg='red')}")
            sys.exit(1)
        except FileNotFoundError as error:
            click.echo("Invalid source directory")
            click.echo(f"The path does not exist or is not accessible: {error}")
        else:
            break

    config = {
        "default_source": source,
        "default_destination": "",
        "auto_stage_enabled": False,
        "default_output_format": "markdown",
    }

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file)

    click.echo(f"{click.style('Configuration file created', fg='green')}")


def read_config(config_file_path: Path) -> dict:
    """
    Read the config file.

    Args:
        config_file_path: The path to the config file.

    Returns:
        The config file as a dictionary.
    """
    try:
        with open(config_file_path, "r", encoding="UTF-8") as file:
            config = json.load(file)

    except json.JSONDecodeError:
        write_default_config(config_file_path)
        with open(config_file_path, "r", encoding="UTF-8") as file:
            config = json.load(file)

    return config


def set_default_source(source: str) -> None:
    """
    Set the default source directory.

    Args:
        source: The default source directory.
    """
    try:
        source = Path(source).resolve(strict=True)
    except FileNotFoundError as error:
        click.echo(f"Invalid source directory: {error}")
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_source"] = source

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file)


def set_default_destination(destination: str) -> None:
    """
    Set the default destination directory.

    Args:
        destination: The default destination directory.
    """
    try:
        destination = Path(destination).resolve(strict=True)
    except FileNotFoundError as error:
        click.echo(f"Invalid destination directory: {error}")
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_destination"] = destination

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file)


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

    # if default_destination:
    #     return Path(default_destination)

    return Path.cwd()


def is_git_repo() -> bool:
    """
    Check if the current directory is a git repository.

    Returns:
        True if the current directory is a git repository, False otherwise.
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
    Get the destination directory for a git repository.

    Returns:
        The destination directory for a git repository.
    """
    try:
        git_root = (
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

    git_root = Path(git_root)

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
    Set whether screenshots are automatically staged when copied to a git repository.

    Args:
        auto_stage_enabled: Whether screenshots are automatically staged when copied to a git repo.
    """
    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["auto_stage_enabled"] = auto_stage_enabled

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file)


def set_default_output_format(output_format: str) -> None:
    """
    Set the default output format.

    Args:
        output_format: The default output format.
    """
    if output_format not in ["markdown", "HTML", "plain_text"]:
        click.echo(f"Invalid output format: {output_format}")
        sys.exit(1)

    config_file_path = get_config_file_path()
    config = read_config(config_file_path)
    config["default_output_format"] = output_format

    with open(config_file_path, "w", encoding="UTF-8") as file:
        json.dump(config, file)


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
    "-a",
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
    """
    if source:
        set_default_source(source)

    if destination:
        set_default_destination(destination)

    if auto_stage_enabled:
        set_auto_stage(auto_stage_enabled)

    if output_format:
        set_default_output_format(output_format)
