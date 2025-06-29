import sys
from pathlib import Path

from .cli import parse_arguments
from .server import start_server


def main() -> None:
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


if __name__ == "__main__":
    main()
