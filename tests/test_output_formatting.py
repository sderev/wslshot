from __future__ import annotations

import sys
from pathlib import Path

import pytest
from wslshot import cli


def test_print_formatted_path_markdown_relative_to_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test markdown format with relative path adds leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("assets/images/screenshot_abc123.png"),)
    cli.print_formatted_path("markdown", screenshots, relative_to_repo=True)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == "![screenshot_abc123.png](/assets/images/screenshot_abc123.png)"
    assert output_lines[0]["err"] is False


def test_print_formatted_path_markdown_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test markdown format with absolute path has no leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("/home/user/screenshots/screenshot_abc123.png"),)
    cli.print_formatted_path("markdown", screenshots, relative_to_repo=False)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == "![screenshot_abc123.png](/home/user/screenshots/screenshot_abc123.png)"
    assert output_lines[0]["err"] is False


def test_print_formatted_path_markdown_multiple_screenshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test markdown format with multiple screenshots outputs each on separate line."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (
        Path("assets/images/screenshot_abc123.png"),
        Path("assets/images/animated_def456.gif"),
    )
    cli.print_formatted_path("markdown", screenshots, relative_to_repo=True)

    assert len(output_lines) == 2
    assert output_lines[0]["msg"] == "![screenshot_abc123.png](/assets/images/screenshot_abc123.png)"
    assert output_lines[1]["msg"] == "![animated_def456.gif](/assets/images/animated_def456.gif)"
    assert all(line["err"] is False for line in output_lines)


def test_print_formatted_path_html_relative_to_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test HTML format with relative path adds leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("assets/images/screenshot_abc123.png"),)
    cli.print_formatted_path("html", screenshots, relative_to_repo=True)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == '<img src="/assets/images/screenshot_abc123.png" alt="screenshot_abc123.png">'
    assert output_lines[0]["err"] is False


def test_print_formatted_path_html_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test HTML format with absolute path has no leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("/home/user/screenshots/screenshot_abc123.png"),)
    cli.print_formatted_path("html", screenshots, relative_to_repo=False)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == '<img src="/home/user/screenshots/screenshot_abc123.png" alt="screenshot_abc123.png">'
    assert output_lines[0]["err"] is False


def test_print_formatted_path_html_multiple_screenshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test HTML format with multiple screenshots outputs each on separate line."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (
        Path("assets/images/screenshot_abc123.png"),
        Path("assets/images/animated_def456.gif"),
    )
    cli.print_formatted_path("html", screenshots, relative_to_repo=True)

    assert len(output_lines) == 2
    assert output_lines[0]["msg"] == '<img src="/assets/images/screenshot_abc123.png" alt="screenshot_abc123.png">'
    assert output_lines[1]["msg"] == '<img src="/assets/images/animated_def456.gif" alt="animated_def456.gif">'
    assert all(line["err"] is False for line in output_lines)


def test_print_formatted_path_plain_text_relative_to_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test plain text format with relative path adds leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("assets/images/screenshot_abc123.png"),)
    cli.print_formatted_path("plain_text", screenshots, relative_to_repo=True)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == "/assets/images/screenshot_abc123.png"
    assert output_lines[0]["err"] is False


def test_print_formatted_path_plain_text_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test plain text format with absolute path has no leading slash."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (Path("/home/user/screenshots/screenshot_abc123.png"),)
    cli.print_formatted_path("plain_text", screenshots, relative_to_repo=False)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == "/home/user/screenshots/screenshot_abc123.png"
    assert output_lines[0]["err"] is False


def test_print_formatted_path_plain_text_multiple_screenshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test plain text format with multiple screenshots outputs each on separate line."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (
        Path("assets/images/screenshot_abc123.png"),
        Path("assets/images/animated_def456.gif"),
    )
    cli.print_formatted_path("plain_text", screenshots, relative_to_repo=True)

    assert len(output_lines) == 2
    assert output_lines[0]["msg"] == "/assets/images/screenshot_abc123.png"
    assert output_lines[1]["msg"] == "/assets/images/animated_def456.gif"
    assert all(line["err"] is False for line in output_lines)


def test_print_formatted_path_invalid_format_exits_with_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test invalid format string exits with code 1 and writes to stderr."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    exit_codes: list[int] = []

    def mock_exit(code: int) -> None:
        exit_codes.append(code)

    monkeypatch.setattr("click.echo", mock_echo)
    monkeypatch.setattr(sys, "exit", mock_exit)

    screenshots = (Path("assets/images/screenshot_abc123.png"),)
    cli.print_formatted_path("invalid_format", screenshots, relative_to_repo=True)

    assert len(output_lines) == 1
    assert output_lines[0]["msg"] == "Invalid output format: invalid_format"
    assert output_lines[0]["err"] is True
    assert exit_codes == [1]


def test_print_formatted_path_preserves_filename_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that filename extraction preserves special characters and extensions."""
    output_lines: list[dict[str, str | bool]] = []

    def mock_echo(msg: str, err: bool = False) -> None:
        output_lines.append({"msg": msg, "err": err})

    monkeypatch.setattr("click.echo", mock_echo)

    screenshots = (
        Path("assets/images/screenshot_with-dashes_123.png"),
        Path("assets/images/file.with.dots.jpeg"),
    )
    cli.print_formatted_path("markdown", screenshots, relative_to_repo=True)

    assert len(output_lines) == 2
    assert output_lines[0]["msg"] == "![screenshot_with-dashes_123.png](/assets/images/screenshot_with-dashes_123.png)"
    assert output_lines[1]["msg"] == "![file.with.dots.jpeg](/assets/images/file.with.dots.jpeg)"
    assert all(line["err"] is False for line in output_lines)
