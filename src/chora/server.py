#!/usr/bin/env python3
"""
chora server implementation.
"""

from http.server import HTTPServer
from pathlib import Path

from .handler import create_handler


def start_server(root_path: Path, host: str, port: int) -> None:
    """Start the HTTP server with the given configuration.

    Args:
        root_path: Path to the root directory for mock responses
        host: Host to bind the server to
        port: Port to run the server on
    """
    handler = create_handler(root_path)
    server = HTTPServer((host, port), handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()
