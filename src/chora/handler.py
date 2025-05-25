"""
HTTP request handler for chora server.
"""

from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse


class ChoraHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves responses based on file system structure."""

    def __init__(self, *args, root_dir, **kwargs):
        self.root_dir = Path(root_dir)
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        """Override __getattr__ to handle unsupported methods."""
        if item.startswith("do_"):
            return lambda: self._handle_request(item[3:])
        raise AttributeError(f"Method {item} not supported.")

    def get_handler(self, directory):
        """Get the handler for the request based on the directory structure."""
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise ValueError(f"Invalid directory: {directory}")

        if (directory / "HANDLER").exists():
            raise NotImplementedError("Custom handlers are not implemented yet.")

        return self._static_handler

    def _static_handler(self, directory):
        status_file = directory / "STATUS"
        status_code = int(status_file.read_text().strip())

        data_file = directory / "DATA"
        response_data = data_file.read_bytes()
        response_headers = {}

        headers_file = directory / "HEADERS"
        headers_content = headers_file.read_text().strip()
        for line in headers_content.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                response_headers[key.strip()] = value.strip()
        return status_code, response_data, response_headers

    def _handle_request(self, method):
        """Handle HTTP request by looking up response in file system."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path.strip("/")
        query_string = parsed_url.query

        method_dir = self.root_dir / path / method
        if query_string:
            method_dir = method_dir / query_string

        handler = self.get_handler(method_dir)
        status_code, data, headers = handler(method_dir)

        self.send_response(status_code)

        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

        self.wfile.write(data)

        print(f"{method} {self.path} -> {status_code}")


def create_handler(root_dir):
    def handler(*args, **kwargs):
        return ChoraHTTPRequestHandler(root_dir=root_dir, *args, **kwargs)

    return handler
