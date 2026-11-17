"""Command line entry points for the FrameViz Python SDK."""

import argparse
from importlib.metadata import version
from pathlib import Path

from ._examples import download_examples


def main():
    parser = argparse.ArgumentParser(prog="python -m frameviz", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    examples = commands.add_parser("download-examples", help="Get examples for this SDK version")
    examples.add_argument("--output", type=Path, default=Path("frameviz-examples"))
    examples.add_argument("--asset-base", help="Directory URL for the version's ZIP and SHA256SUMS")
    args = parser.parse_args()
    try:
        output = download_examples(version("frameviz"), args.output, args.asset_base)
    except (OSError, ValueError) as error:
        parser.exit(1, f"FrameViz: {error}\n")
    print(output)


if __name__ == "__main__":
    main()
