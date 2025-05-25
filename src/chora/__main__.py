import argparse
import sys
import tomllib
from pathlib import Path

from .server import start_server


def load_config_from_file(pyproject_path: Path) -> dict:
    """Load configuration from pyproject.toml file.

    Returns:
        dict: Configuration from [tool.chora] section, or empty dict if not found
    """
    if not pyproject_path.exists():
        return {}

    try:
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f).get("tool", {}).get("chora", {})
    except Exception as e:
        print(f"Warning: Could not read pyproject.toml: {e}")
        return {}


def parse_arguments() -> argparse.Namespace:
    defaults = {
        "root": "./chora-root",
        "port": 8000,
        "host": "localhost",
    }

    # TODO: make this configurable
    pyproject_path = Path("pyproject.toml")
    config = load_config_from_file(pyproject_path)

    for key, value in config.items():
        defaults[key] = value

    parser = argparse.ArgumentParser(
        description="chora - A mock HTTP server based on file system structure"
    )
    parser.add_argument(
        "--root",
        default=defaults["root"],
        help=f"Path to the directory containing your mock API structure (default: {defaults['root']})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=defaults["port"],
        help=f"Port to run the server on (default: {defaults['port']})",
    )
    parser.add_argument(
        "--host",
        default=defaults["host"],
        help=f"Host to bind the server to (default: {defaults['host']})",
    )

    return parser.parse_args()


def main():
    """Main entry point for chora server."""
    args = parse_arguments()

    # Validate root directory
    root_path = Path(args.root)
    if not root_path.exists():
        print(f"Error: Root directory '{args.root}' does not exist.")
        sys.exit(1)

    if not root_path.is_dir():
        print(f"Error: Root path '{args.root}' is not a directory.")
        sys.exit(1)

    print("Starting chora server...")
    print(f"  Root directory: {root_path.absolute()}")
    print(f"  Server address: http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop the server")

    start_server(root_path, args.host, args.port)


main()
