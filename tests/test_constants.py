from __future__ import annotations

import pytest

from wslshot import cli


def test_valid_output_formats_constant_values() -> None:
    assert hasattr(cli, "VALID_OUTPUT_FORMATS")
    assert cli.VALID_OUTPUT_FORMATS == ("markdown", "html", "text")
    assert isinstance(cli.VALID_OUTPUT_FORMATS, tuple)


def test_valid_output_formats_is_immutable() -> None:
    with pytest.raises(TypeError):
        cli.VALID_OUTPUT_FORMATS[0] = "markdown"
