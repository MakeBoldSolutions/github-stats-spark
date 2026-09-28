"""Regression coverage for CLI parser and dispatch helpers."""

import sys

import pytest

from spark import cli
from spark.cli_argument_builders import build_main_parser
from spark.cli_output_layout import build_output_layout, slugify_username


def test_build_main_parser_supports_unified_command():
    parser = build_main_parser()

    args = parser.parse_args(["unified", "--user", "markhazleton"])

    assert args.command == "unified"
    assert args.user == "markhazleton"


def test_build_output_layout_scopes_to_user_paths():
    layout = build_output_layout("Mark Hazleton", "data")

    assert slugify_username("Mark Hazleton") == "mark-hazleton"
    assert layout["data_dir"].as_posix() == "data/users/mark-hazleton"
    assert layout["artifact_root"].as_posix() == "output/users/mark-hazleton"


def test_main_dispatches_to_unified_handler(monkeypatch):
    captured = {}

    def fake_handle_unified(args, logger):
        captured["command"] = args.command
        captured["user"] = args.user

    monkeypatch.setattr(cli, "handle_unified", fake_handle_unified)
    monkeypatch.setattr(sys, "argv", ["spark", "unified", "--user", "markhazleton"])

    cli.main()

    assert captured == {"command": "unified", "user": "markhazleton"}


def test_main_prints_help_when_no_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["spark"])

    with pytest.raises(SystemExit):
        cli.main()

    captured = capsys.readouterr()
    assert "Available commands" in captured.out
