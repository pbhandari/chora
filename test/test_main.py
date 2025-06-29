import os
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest

from chora.__main__ import main


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Fixture that provides the default root directory."""
    root_dir = tmp_path / "test-root"
    root_dir.mkdir(exist_ok=True)
    return root_dir


@pytest.fixture
def host() -> str:
    """Fixture that provides the default host."""
    return "localhost"


@pytest.fixture
def port() -> int:
    """Fixture that provides the default port."""
    return 8000


@pytest.fixture(autouse=True)
def mock_start_server() -> Generator[Mock, None, None]:
    """Fixture that provides a mock for start_server."""
    with patch("chora.__main__.start_server") as mock:
        yield mock


@pytest.fixture
def mock_parse_arguments(
    root: Path, host: str, port: int
) -> Generator[Mock, None, None]:
    """Fixture that provides a mock for parse_arguments."""
    with patch("chora.__main__.parse_arguments") as mock:
        mock_args = Mock()
        mock_args.root = root
        mock_args.host = host
        mock_args.port = port
        mock.return_value = mock_args
        yield mock


class TestMain:
    def test_successful_execution(
        self,
        mock_parse_arguments: Mock,
        mock_start_server: Mock,
        root: Path,
        host: str,
        port: int,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test successful execution of main function."""
        main()

        # Verify parse_arguments was called
        mock_parse_arguments.assert_called_once()
        mock_start_server.assert_called_once_with(root, host, port)

        # Verify print statements were called
        captured = capsys.readouterr()
        expected_output = (
            "Starting chora server...\n"
            f"  Root directory: {root.absolute()}\n"
            "  Server address: http://localhost:8000\n"
            "  Press Ctrl+C to stop the server\n"
        )
        assert captured.out == expected_output

    @patch("sys.exit", side_effect=SystemExit)
    @pytest.mark.parametrize("root", [Path("/absolute/path"), Path("relative/path")])
    def test_root_directory_does_not_exist(
        self,
        mock_exit: Mock,
        mock_parse_arguments: Mock,
        root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit):
            main()

        # Verify error message was printed to stdout
        captured = capsys.readouterr()
        assert f"Error: Root directory '{root}' does not exist." in captured.out

    @patch("sys.exit", side_effect=SystemExit)
    def test_root_path_is_not_directory(
        self,
        mock_exit: Mock,
        mock_parse_arguments: Mock,
        mock_start_server: Mock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test main function when root path is not a directory."""
        # Create a file instead of directory
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("")
        mock_parse_arguments.return_value.root = test_file

        # Execute main
        with pytest.raises(SystemExit):
            main()

        # Verify error message was printed to stdout
        captured = capsys.readouterr()
        assert f"Error: Root path '{test_file}' is not a directory." in captured.out

    def test_with_relative_path(
        self,
        mock_parse_arguments: Mock,
        mock_start_server: Mock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test main function with relative path that gets converted to absolute."""
        # Create a subdirectory
        # Change to the temp directory so relative path works
        os.chdir(tmp_path)

        subdir = "api"
        mock_parse_arguments.return_value.root = tmp_path / subdir
        (tmp_path / subdir).mkdir()

        # Execute main
        main()

        mock_start_server.assert_called_once()
        call_args = mock_start_server.call_args[0]
        assert call_args[0], Path("api")
        assert call_args[1] == "localhost"
        assert call_args[2] == 8000

    def test_handles_keyboard_interrupt(
        self,
        mock_parse_arguments: Mock,
        mock_start_server: Mock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that main function handles KeyboardInterrupt from start_server."""
        mock_start_server.side_effect = KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            main()

        mock_parse_arguments.assert_called_once()
        mock_start_server.assert_called_once()

    def test_path_object_conversion(
        self,
        mock_parse_arguments: Mock,
        mock_start_server: Mock,
        root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_parse_arguments.return_value.root = str(root)
        main()

        mock_start_server.assert_called_once()
        root_arg = mock_start_server.call_args[0][0]
        assert isinstance(root_arg, Path)
        assert root_arg == root
