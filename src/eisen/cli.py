"""Command-line entry point: `eisen extract` and `eisen evaluate`."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eisen",
        description="Haalt eisen en wensen uit contract-pdf's en zet ze klaar in Excel.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("extract", help="Eisen uit de pdf's halen en naar Excel schrijven.")
    sub.add_parser("evaluate", help="Excel-uitvoer vergelijken met de referentielijst.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"'{args.command}' is nog niet geïmplementeerd.", file=sys.stderr)
    return 1
