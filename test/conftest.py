import json
import socket
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from typing import Any, Dict, Generator, Tuple
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from chora.handler import create_handler


@pytest.fixture
def port() -> int:
    """Fixture that provides an available port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))  # 0 means let the OS choose an available port
        return s.getsockname()[1]


class TestClient:
    """Test client for making requests to the chora server."""

    def __init__(self, base_url: str, tmp_path: Path) -> None:
        self.base_url = base_url
        self.tmp_path = tmp_path

    def get(self, path: str) -> "TestResponse":
        """Make a GET request to the server."""
        return self._request("GET", path)

    def _request(self, method: str, path: str, data: Any = None) -> "TestResponse":
        """Make an HTTP request and return a response object."""
        url = f"{self.base_url}{path}"

        try:
            response = urlopen(url)
            return TestResponse(response)
        except HTTPError as e:
            return TestResponse(e)


class TestResponse:
    """Wrapper for HTTP responses in tests."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.status_code = (
            response.status if hasattr(response, "status") else response.code
        )
        self.headers = dict(response.headers) if hasattr(response, "headers") else {}

        self.data = response.read()

    @property
    def text(self) -> str:
        """Get response data as text."""
        return self.data.decode("utf-8")

    def json(self) -> Any:
        """Parse response data as JSON."""
        return json.loads(self.text)

    def get_header(self, name: str, default: Any = None) -> Any:
        """Get a specific header value."""
        return self.headers.get(name, default)


@pytest.fixture
def test_server(
    tmp_path: Path, port: int
) -> Generator[Tuple[HTTPServer, Path, int], None, None]:
    """Fixture that provides a running test server."""
    handler = create_handler(tmp_path)
    server = HTTPServer(("127.0.0.1", port), handler)

    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Give the server a moment to start
    time.sleep(0.1)

    yield server, tmp_path, port

    # Cleanup
    server.shutdown()
    server.server_close()


@pytest.fixture
def test_client(test_server: Tuple[HTTPServer, Path, int]) -> TestClient:
    """Fixture that provides a test client for making HTTP requests."""
    _, tmp_path, port = test_server
    base_url = f"http://127.0.0.1:{port}"
    return TestClient(base_url, tmp_path)


def make_static_route(
    path: Path,
    headers: Dict[str, str] | None = None,
    status_code: int = 200,
    body: Any = None,
) -> None:
    """Create a static route with the given response data."""
    path.mkdir(parents=True, exist_ok=True)

    # Data
    data_file = path / "DATA"
    data_file.write_text(json.dumps(body or {}))

    # Headers
    headers_file = path / "HEADERS"
    header_lines = []
    for key, value in (headers or {}).items():
        header_lines.append(f"{key}: {value}")
    headers_file.write_text("\n".join(header_lines))

    # Status
    status_file = path / "STATUS"
    status_file.write_text(str(status_code))
