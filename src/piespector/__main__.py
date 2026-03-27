from __future__ import annotations

import argparse

from piespector import __version__
from piespector.app import PiespectorApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="piespector",
        description="Terminal-first API client for organized request workflows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    PiespectorApp().run()


if __name__ == "__main__":
    main()
