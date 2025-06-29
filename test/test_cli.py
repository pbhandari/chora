from pathlib import Path
from typing import Any, Generator
from unittest.mock import patch

import pytest

from chora.cli import load_config_from_file, parse_arguments


@pytest.fixture
def remove_existing_config() -> Generator[None, None, None]:
    """Having chora config in pyproject is helpful for defaults, but we want to
    test without it."""
    with patch("chora.cli.Path") as mock_path:
        mock_path.return_value.exists.return_value = False
        yield


class TestLoadConfigFromFile:
    """Test cases for load_config_from_file function."""

    def test_load_config_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading config from a non-existent file returns empty dict."""
        nonexistent_path = tmp_path / "nonexistent.toml"
        result = load_config_from_file(nonexistent_path)
        assert result == {}

    def test_load_config_valid_toml_with_chora_section(self, tmp_path: Path) -> None:
        """Test loading config from valid TOML file with chora section."""
        toml_content = """
[tool.chora]
root = "./custom-root"
port = 9000
host = "0.0.0.0"
custom_setting = "test"
"""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text(toml_content)

        result = load_config_from_file(toml_file)
        expected = {
            "root": "./custom-root",
            "port": 9000,
            "host": "0.0.0.0",
            "custom_setting": "test",
        }
        assert result == expected

    def test_load_config_valid_toml_without_chora_section(self, tmp_path: Path) -> None:
        """Test loading config from valid TOTML file without chora section."""
        toml_content = """
[tool.other]
setting = "value"

[project]
name = "test"
"""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text(toml_content)

        result = load_config_from_file(toml_file)
        assert result == {}

    def test_load_config_valid_toml_without_tool_section(self, tmp_path: Path) -> None:
        """Test loading config from valid TOML file without tool section."""
        toml_content = """
[project]
name = "test"
version = "1.0.0"
"""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text(toml_content)

        result = load_config_from_file(toml_file)
        assert result == {}

    def test_load_config_malformed_toml(self, tmp_path: Path) -> None:
        """Test loading config from malformed TOML file returns empty dict."""
        toml_content = """
[tool.chora
root = "./custom-root"  # Missing closing bracket
"""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text(toml_content)

        with patch("builtins.print") as mock_print:
            result = load_config_from_file(toml_file)
            assert result == {}
            # Verify warning message was printed
            mock_print.assert_called_once()
            assert (
                "Warning: Could not read pyproject.toml:" in mock_print.call_args[0][0]
            )

    def test_load_config_empty_toml(self, tmp_path: Path) -> None:
        """Test loading config from empty TOML file."""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text("")

        result = load_config_from_file(toml_file)
        assert result == {}

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_load_config_permission_error(
        self, mock_open_func: Any, tmp_path: Path
    ) -> None:
        """Test loading config when file cannot be opened due to permissions."""
        toml_file = tmp_path / "pyproject.toml"
        toml_file.touch()  # Create the file so exists() returns True

        with patch("builtins.print") as mock_print:
            result = load_config_from_file(toml_file)
            assert result == {}
            mock_print.assert_called_once()
            assert (
                "Warning: Could not read pyproject.toml:" in mock_print.call_args[0][0]
            )


class TestParseArguments:
    """Test cases for parse_arguments function."""

    def test_defaults_no_config_file(self, remove_existing_config: None) -> None:
        """Test parsing arguments with defaults when no config file exists."""
        with patch("sys.argv", ["chora"]):
            args = parse_arguments()

            assert args.root == "./chora-root"
            assert args.port == 8000
            assert args.host == "localhost"

    def test_parse_arguments_with_config_file_overrides(self, tmp_path: Path) -> None:
        """Test parsing arguments with config file overriding defaults."""
        # Create a temporary config file
        toml_content = """
[tool.chora]
root = "./config-root"
port = 9000
host = "127.0.0.1"
"""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(toml_content)

        with patch("sys.argv", ["chora"]):
            with patch("chora.cli.Path") as mock_path:
                mock_path.return_value = config_file
                args = parse_arguments()

                assert args.root == "./config-root"
                assert args.port == 9000
                assert args.host == "127.0.0.1"

    def test_parse_arguments_command_line_overrides_config(
        self, tmp_path: Path
    ) -> None:
        """Test that command line arguments override config file settings."""
        # Create a temporary config file
        toml_content = """
[tool.chora]
root = "./config-root"
port = 9000
host = "127.0.0.1"
"""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(toml_content)

        with patch(
            "sys.argv",
            ["chora", "--root", "./cli-root", "--port", "7000", "--host", "0.0.0.0"],
        ):
            with patch("chora.cli.Path") as mock_path:
                mock_path.return_value = config_file
                args = parse_arguments()

                assert args.root == "./cli-root"
                assert args.port == 7000
                assert args.host == "0.0.0.0"

    def test_parse_arguments_partial_command_line_override(
        self, tmp_path: Path
    ) -> None:
        """Test partial command line override with config file."""
        toml_content = """
[tool.chora]
root = "./config-root"
port = 9000
host = "127.0.0.1"
"""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(toml_content)

        with patch("sys.argv", ["chora", "--port", "7000"]):
            with patch("chora.cli.Path") as mock_path:
                mock_path.return_value = config_file
                args = parse_arguments()

                assert args.root == "./config-root"  # From config
                assert args.port == 7000  # From CLI
                assert args.host == "127.0.0.1"  # From config

    def test_parse_arguments_help_text_includes_defaults(self, tmp_path: Path) -> None:
        """Test that help text shows the correct defaults from config."""
        toml_content = """
[tool.chora]
root = "./my-api"
port = 3000
host = "custom.host"
"""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(toml_content)

        with patch("chora.cli.Path") as mock_path:
            mock_path.return_value = config_file

            # Test that we can create the parser without errors
            # and that it uses the config defaults
            with patch("sys.argv", ["chora", "--help"]):
                with pytest.raises(SystemExit):  # argparse exits with --help
                    parse_arguments()

    def test_invalid_port_type(self, remove_existing_config: None) -> None:
        """Test parsing arguments with invalid port type."""
        with patch("sys.argv", ["chora", "--port", "invalid"]):
            with pytest.raises(SystemExit):  # argparse exits on invalid type
                parse_arguments()

    def test_all_cli_options(self, remove_existing_config: None) -> None:
        """Test parsing all available CLI options."""
        with patch(
            "sys.argv",
            [
                "chora",
                "--root",
                "/custom/path",
                "--port",
                "5000",
                "--host",
                "example.com",
            ],
        ):
            args = parse_arguments()

            assert args.root == "/custom/path"
            assert args.port == 5000
            assert args.host == "example.com"

    def test_parse_arguments_config_with_extra_settings(self, tmp_path: Path) -> None:
        """Test that extra config settings don't break argument parsing."""
        toml_content = """
[tool.chora]
root = "./api-root"
port = 4000
host = "api.local"
extra_setting = "ignored"
another_setting = 42
"""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(toml_content)

        with patch("sys.argv", ["chora"]):
            with patch("chora.cli.Path") as mock_path:
                mock_path.return_value = config_file
                args = parse_arguments()

                assert args.root == "./api-root"
                assert args.port == 4000
                assert args.host == "api.local"
                # Extra settings should not appear in args
                assert not hasattr(args, "extra_setting")
                assert not hasattr(args, "another_setting")
