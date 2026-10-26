import pytest

from eisen.cli import build_parser


def test_parser_knows_both_commands():
    parser = build_parser()
    assert parser.parse_args(["extract"]).command == "extract"
    assert parser.parse_args(["evaluate"]).command == "evaluate"


def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
