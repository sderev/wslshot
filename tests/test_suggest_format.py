"""
Unit tests for the suggest_format helper.
"""

from __future__ import annotations

import pytest

from wslshot import cli

VALID_FORMATS = list(cli.VALID_OUTPUT_FORMATS)


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("mark", "markdown"),
        ("htm", "html"),
        ("tex", "text"),
        ("down", "markdown"),
    ],
)
def test_suggest_format_matches_substrings(user_input: str, expected: str) -> None:
    """Return suggestions when the input is a substring of valid formats."""
    suggestion = cli.suggest_format(user_input, VALID_FORMATS)

    assert suggestion == f"Did you mean: {expected}?"


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("markdwon", "markdown"),
        ("mrk", "markdown"),
        ("htlm", "html"),
        ("txt", "text"),
    ],
)
def test_suggest_format_matches_bigrams(user_input: str, expected: str) -> None:
    """Return suggestions based on shared bigrams."""
    suggestion = cli.suggest_format(user_input, VALID_FORMATS)

    assert suggestion == f"Did you mean: {expected}?"


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("MARK", "markdown"),
        ("Html", "html"),
        ("TeXt", "text"),
    ],
)
def test_suggest_format_is_case_insensitive(user_input: str, expected: str) -> None:
    """Handle inputs regardless of letter casing."""
    suggestion = cli.suggest_format(user_input, VALID_FORMATS)

    assert suggestion == f"Did you mean: {expected}?"


@pytest.mark.parametrize("user_input", ["xyz", "json", "web"])
def test_suggest_format_returns_empty_for_unknown_inputs(user_input: str) -> None:
    """Return empty string when no formats match."""
    suggestion = cli.suggest_format(user_input, VALID_FORMATS)

    assert suggestion == ""


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("", "Did you mean: markdown, html, text?"),
        ("   ", ""),
        ("###", ""),
    ],
)
def test_suggest_format_handles_edge_cases(user_input: str, expected: str) -> None:
    """Handle edge-case inputs gracefully."""
    suggestion = cli.suggest_format(user_input, VALID_FORMATS)

    assert suggestion == expected
