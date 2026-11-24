"""Command line entry points for the FrameViz Python SDK."""

import argparse
from importlib.metadata import version
from pathlib import Path

from ._examples import download_examples
from ._host_install import install_host


def main():
    parser = argparse.ArgumentParser(prog="python -m frameviz", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    examples = commands.add_parser("download-examples", help="Get examples for this SDK version")
    examples.add_argument("--output", type=Path, default=Path("frameviz-examples"))
    examples.add_argument("--asset-base", help="Directory URL for the version's ZIP and SHA256SUMS")
    runtime = commands.add_parser("install-host", help="Install the runtime for this SDK")
    runtime.add_argument("--path", type=Path, help="Use a local runtime archive, App, or executable")
    args = parser.parse_args()
    try:
        if args.command == "install-host":
            output = install_host(path=args.path)
        else:
            output = download_examples(version("frameviz"), args.output, args.asset_base)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"FrameViz: {error}\n")
    print(output)


if __name__ == "__main__":
    main()
