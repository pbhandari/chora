"""
HTTP request handler for chora server.
"""

import os
import subprocess
import tempfile
from functools import partial
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


class ChoraHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves responses based on file system structure."""

    def __init__(
        self,
        *args,
        root_dir: str | Path,
        tmpdir: str | Path = "/tmp/chora_cache",
        **kwargs,
    ):
        self.root_dir = Path(root_dir)
        self.tmpdir = Path(tmpdir)
        super().__init__(*args, **kwargs)

    def __getattr__(self, item: str) -> Callable:
        if item.startswith("do_"):
            return partial(self._handle_request, item[3:])
        raise AttributeError(f"Method {item} not supported.")

    def _get_directory(self, directory: Path) -> Path | None:
        if directory.is_dir():
            return directory

        parts = list(directory.parts)
        for i in range(len(parts), 0, -1):
            candidate = Path(*parts[: i - 1], "__TEMPLATE__", *parts[i:])
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None

    def get_handler(
        self, directory: Path
    ) -> Callable[[], tuple[int, bytes, dict[str, str]]]:
        """Get the handler for the request based on the directory structure."""
        directory = self._get_directory(directory)  # type: ignore[assignment]
        if not directory:
            raise FileNotFoundError(f"Directory not found: {directory}")

        if (directory / "HANDLE").exists():
            return self._dynamic_handler(directory)

        return partial(self._static_handler, directory)

    def _dynamic_handler(
        self, directory: Path
    ) -> Callable[[], tuple[int, bytes, dict[str, str]]]:
        handler = (directory / "HANDLE").absolute()

        if not os.access(handler, os.X_OK):
            raise PermissionError(f"HANDLE script is not executable: {handler}")

        proc = subprocess.run(
            [str(handler.absolute()), str(self.tmpdir)],
            capture_output=True,
            text=True,
            check=True,
        )
        output = proc.stdout.strip()
        response_dir = Path(output)
        if not response_dir.is_absolute():
            response_dir = handler.parent / response_dir

        print(f"Dynamic handler output: {response_dir}")
        return self.get_handler(response_dir)

    def _static_handler(self, directory: Path) -> tuple[int, bytes, dict[str, str]]:
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

    def _cache_request(self) -> None:
        (self.tmpdir / "REQUEST").write_text(str(self.requestline))

        with open(self.tmpdir / "HEADERS", "w") as f:
            for k, v in self.headers.items():
                f.write(f"{k}: {v}\n")

        # Read request body if present
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        (self.tmpdir / "DATA").write_text(str(body))

    def _handle_request(self, method: str) -> None:
        """Handle HTTP request by looking up response in file system."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.strip("/")

            method_dir = self.root_dir / path / method

            with tempfile.TemporaryDirectory() as tmpdir:
                self.tmpdir = Path(tmpdir)
                self._cache_request()
                handler = self.get_handler(method_dir)
                status_code, data, headers = handler()

                self.send_response(status_code)

                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()

                self.wfile.write(data)

            print(f"{method} {self.path} -> {status_code}")

        except FileNotFoundError:
            self._send_error_response(404, "Not Found")

        except PermissionError:
            self._send_error_response(403, "Forbidden")

        except (ValueError, subprocess.CalledProcessError) as e:
            self._send_error_response(500, f"Internal Server Error: {str(e)}")

    def _send_error_response(self, status_code: int, message: str) -> None:
        """Send a simple error response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode())
        print(f"ERROR {self.path} -> {status_code}: {message}")


def create_handler(
    root_dir: str | Path, tmpdir: str | Path = ""
) -> Callable[..., ChoraHTTPRequestHandler]:
    def handler(*args, **kwargs) -> ChoraHTTPRequestHandler:
        return ChoraHTTPRequestHandler(
            root_dir=root_dir, tmpdir=tmpdir, *args, **kwargs
        )

    return handler
