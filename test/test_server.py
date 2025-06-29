"""
Tests for the chora server module.
"""

import threading
import time
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from chora.server import cleanup, start_server


@pytest.fixture
def mock_server() -> MagicMock:
    """Fixture that provides a mock server instance."""
    return MagicMock()


@pytest.fixture
def mock_http_server() -> Generator[MagicMock, None, None]:
    """Fixture that provides a mock HTTPServer."""
    with patch("chora.server.HTTPServer") as mock:
        yield mock


@pytest.fixture
def mock_create_handler() -> Generator[MagicMock, None, None]:
    """Fixture that provides a mock create_handler function."""
    with patch("chora.server.create_handler") as mock:
        yield mock


@pytest.fixture
def mock_atexit() -> Generator[MagicMock, None, None]:
    """Fixture that provides a mock atexit.register function."""
    with patch("atexit.register") as mock:
        yield mock


class TestServerCleanup:
    """Test the cleanup function behavior."""

    def test_cleanup_calls_server_methods(self, mock_server: MagicMock) -> None:
        """Test that cleanup properly calls server shutdown and close methods."""
        # Call cleanup
        cleanup(mock_server)

        # Verify the methods were called
        mock_server.shutdown.assert_called_once()
        mock_server.server_close.assert_called_once()

    def test_cleanup_handles_shutdown_exception(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that cleanup handles exceptions during server shutdown gracefully."""
        # Create a mock server that raises an exception on shutdown
        mock_server = MagicMock()
        mock_server.shutdown.side_effect = Exception("Shutdown failed")

        # Call cleanup - should not raise an exception
        cleanup(mock_server)

        # Verify shutdown was attempted
        mock_server.shutdown.assert_called_once()
        # server_close should still be called even if shutdown fails
        mock_server.server_close.assert_called_once()

    def test_cleanup_handles_server_close_exception(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that cleanup handles exceptions during server close gracefully."""
        # Create a mock server that raises an exception on server_close
        mock_server = MagicMock()
        mock_server.server_close.side_effect = Exception("Close failed")

        # Call cleanup - should not raise an exception
        cleanup(mock_server)

        # Verify both methods were attempted
        mock_server.shutdown.assert_called_once()
        mock_server.server_close.assert_called_once()


class TestServerStartup:
    """Test server startup and configuration."""

    def test_start_server_creates_server_with_correct_params(
        self,
        mock_atexit: MagicMock,
        mock_create_handler: MagicMock,
        mock_http_server: MagicMock,
    ) -> None:
        """Test that start_server creates HTTPServer with correct parameters."""
        # Setup mocks
        mock_handler = MagicMock()
        mock_create_handler.return_value = mock_handler
        mock_server = MagicMock()
        mock_http_server.return_value = mock_server

        # Mock serve_forever to avoid blocking
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        root_path = Path("/test/root")
        host = "localhost"
        port = 8080

        # Call start_server
        try:
            start_server(root_path, host, port)
        except KeyboardInterrupt:
            pass  # Expected from our mock

        # Verify handler was created with correct root path
        mock_create_handler.assert_called_once_with(root_path)

        # Verify HTTPServer was created with correct parameters
        mock_http_server.assert_called_once_with((host, port), mock_handler)

        # Verify atexit was registered
        mock_atexit.assert_called_once()

    def test_start_server_registers_cleanup_with_atexit(
        self,
        mock_atexit: MagicMock,
        mock_create_handler: MagicMock,
        mock_http_server: MagicMock,
    ) -> None:
        """Test that start_server registers cleanup function with atexit."""
        # Setup mocks
        mock_server = MagicMock()
        mock_http_server.return_value = mock_server
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        root_path = Path("/test/root")

        # Call start_server
        try:
            start_server(root_path, "localhost", 8080)
        except KeyboardInterrupt:
            pass

        # Verify atexit.register was called
        mock_atexit.assert_called_once()

        # Get the registered function and verify it's a partial with our server
        registered_func = mock_atexit.call_args[0][0]
        assert hasattr(registered_func, "func")  # Should be a functools.partial
        assert registered_func.func == cleanup
        assert registered_func.args == (mock_server,)

    def test_start_server_calls_serve_forever(
        self,
        mock_atexit: MagicMock,
        mock_create_handler: MagicMock,
        mock_http_server: MagicMock,
    ) -> None:
        """Test that start_server calls serve_forever on the server."""
        # Setup mocks
        mock_server = MagicMock()
        mock_http_server.return_value = mock_server
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        # Call start_server
        try:
            start_server(Path("/test"), "localhost", 8080)
        except KeyboardInterrupt:
            pass

        # Verify serve_forever was called
        mock_server.serve_forever.assert_called_once()


class TestServerIntegration:
    """Integration tests for the server."""

    def test_server_starts_and_responds_to_requests(self, tmp_path: Path) -> None:
        """Test that the server starts correctly and can handle requests."""
        import json
        import socket
        import urllib.request

        from conftest import make_static_route

        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        # Create test data
        test_path = tmp_path / "test" / "GET"
        make_static_route(
            test_path,
            headers={"Content-Type": "application/json"},
            body={"message": "Hello from test server"},
        )

        # Start server in a separate thread
        server_thread = threading.Thread(
            target=start_server, args=(tmp_path, "127.0.0.1", port), daemon=True
        )
        server_thread.start()

        # Give server time to start
        time.sleep(0.2)

        # Make a request
        url = f"http://127.0.0.1:{port}/test"
        with urllib.request.urlopen(url) as response:
            assert response.getcode() == 200
            assert response.headers.get("Content-Type") == "application/json"
            data = json.loads(response.read().decode())
            assert data == {"message": "Hello from test server"}

    def test_server_handles_multiple_concurrent_requests(self, tmp_path: Path) -> None:
        """Test that the server can handle multiple concurrent requests."""
        import concurrent.futures
        import json
        import socket
        import urllib.request

        from conftest import make_static_route

        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        # Create multiple test endpoints
        for i in range(3):
            test_path = tmp_path / f"test{i}" / "GET"
            make_static_route(
                test_path,
                headers={"Content-Type": "application/json"},
                body={"endpoint": i, "message": f"Response {i}"},
            )

        # Start server
        server_thread = threading.Thread(
            target=start_server, args=(tmp_path, "127.0.0.1", port), daemon=True
        )
        server_thread.start()
        time.sleep(0.2)

        # Make concurrent requests
        def make_request(endpoint_num: int) -> Any:
            url = f"http://127.0.0.1:{port}/test{endpoint_num}"
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request, i) for i in range(3)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # Verify all requests succeeded
        assert len(results) == 3
        endpoint_nums = [result["endpoint"] for result in results]
        assert sorted(endpoint_nums) == [0, 1, 2]


class TestServerErrorHandling:
    """Test server error handling scenarios."""

    def test_start_server_handles_handler_creation_error(
        self, mock_create_handler: MagicMock
    ) -> None:
        """Test that start_server handles errors during handler creation."""
        # Make create_handler raise an exception
        mock_create_handler.side_effect = Exception("Handler creation failed")

        # start_server should propagate the exception
        with pytest.raises(Exception, match="Handler creation failed"):
            start_server(Path("/nonexistent"), "localhost", 8080)

    def test_start_server_handles_server_creation_error(
        self, mock_create_handler: MagicMock, mock_http_server: MagicMock
    ) -> None:
        """Test that start_server handles errors during HTTPServer creation."""
        # Make HTTPServer raise an exception
        mock_http_server.side_effect = OSError("Port already in use")

        # start_server should propagate the exception
        with pytest.raises(OSError, match="Port already in use"):
            start_server(Path("/test"), "localhost", 8080)

    def test_start_server_handles_serve_forever_exception(
        self,
        mock_atexit: MagicMock,
        mock_create_handler: MagicMock,
        mock_http_server: MagicMock,
    ) -> None:
        """Test that start_server handles exceptions from serve_forever."""
        # Setup mocks
        mock_server = MagicMock()
        mock_http_server.return_value = mock_server
        mock_server.serve_forever.side_effect = Exception("Server error")

        # start_server should propagate the exception
        with pytest.raises(Exception, match="Server error"):
            start_server(Path("/test"), "localhost", 8080)

        # Cleanup should still be registered
        mock_atexit.assert_called_once()


class TestAtexitIntegration:
    """Test atexit integration behavior."""

    def test_atexit_cleanup_is_called_on_normal_exit(
        self,
        mock_atexit: MagicMock,
        mock_http_server: MagicMock,
        mock_create_handler: MagicMock,
    ) -> None:
        """Test that atexit cleanup is actually called when Python exits."""
        # This is tricky to test directly, but we can verify the registration
        mock_server = MagicMock()
        mock_http_server.return_value = mock_server
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        try:
            start_server(Path("/test"), "localhost", 8080)
        except KeyboardInterrupt:
            pass

        # Verify registration happened
        assert mock_atexit.called

        # Get the registered function and call it to verify it works
        registered_func = mock_atexit.call_args[0][0]
        registered_func()  # Should not raise an exception

        # Verify the server cleanup methods were called
        mock_server.shutdown.assert_called_once()
        mock_server.server_close.assert_called_once()

    def test_multiple_server_instances_register_separate_cleanup(
        self,
        mock_atexit: MagicMock,
        mock_http_server: MagicMock,
        mock_create_handler: MagicMock,
    ) -> None:
        """Test that multiple server instances each register their own cleanup."""
        # Create two different mock servers
        mock_server1 = MagicMock()
        mock_server2 = MagicMock()
        mock_http_server.side_effect = [mock_server1, mock_server2]

        # Both servers raise KeyboardInterrupt to exit quickly
        mock_server1.serve_forever.side_effect = KeyboardInterrupt()
        mock_server2.serve_forever.side_effect = KeyboardInterrupt()

        # Start first server
        try:
            start_server(Path("/test1"), "localhost", 8081)
        except KeyboardInterrupt:
            pass

        # Start second server
        try:
            start_server(Path("/test2"), "localhost", 8082)
        except KeyboardInterrupt:
            pass

        # Verify atexit.register was called twice
        assert mock_atexit.call_count == 2

        # Get both registered functions
        cleanup1 = mock_atexit.call_args_list[0][0][0]
        cleanup2 = mock_atexit.call_args_list[1][0][0]

        # Call both cleanup functions
        cleanup1()
        cleanup2()

        # Verify each server's cleanup was called
        mock_server1.shutdown.assert_called_once()
        mock_server1.server_close.assert_called_once()
        mock_server2.shutdown.assert_called_once()
        mock_server2.server_close.assert_called_once()
