import pytest
from conftest import TestClient, make_static_route


def test_handle_static(test_client: TestClient) -> None:
    """Test that static routes are handled properly."""
    path = "test"

    assert test_client.tmp_path is not None  # Type assertion for mypy
    test_dir = test_client.tmp_path / path / "GET"
    make_static_route(
        test_dir, headers={"Content-Type": "application/json"}, body={"key": "value"}
    )

    # Make an HTTP request using the test client
    response = test_client.get(f"/{path}")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "application/json"
    assert response.json() == {"key": "value"}


def test_dynamic_handler(test_client: TestClient) -> None:
    """Test that dynamic handlers (HANDLE scripts) are executed properly."""
    path = "dynamic"
    method = "GET"

    # Create the directory structure for dynamic handler
    handler_dir = test_client.tmp_path / path / method
    handler_dir.mkdir(parents=True, exist_ok=True)

    # Create a HANDLE script that returns a path to static content
    handle_script = handler_dir / "HANDLE"
    handle_script.write_text("""#!/bin/sh
echo "static_response"
""")
    handle_script.chmod(0o755)  # Make executable

    # Create the static response that the HANDLE script points to
    response_dir = handler_dir / "static_response"
    make_static_route(
        response_dir, headers={"Content-Type": "text/plain"}, body="Dynamic response"
    )

    # Make request
    response = test_client.get(f"/{path}")

    # Verify dynamic handler was executed and returned static content
    assert response.status_code == 200
    assert response.get_header("Content-Type") == "text/plain"
    assert response.json() == "Dynamic response"


@pytest.mark.parametrize("user_id", ["123", "456", "abc", "user-with-dashes"])
def test_template_matching(test_client: TestClient, user_id: str) -> None:
    """Test that __TEMPLATE__ directories are used when exact path doesn't exist."""
    base_path = "users"
    method = "GET"

    # Create a __TEMPLATE__ directory instead of exact path
    # The handler looks for: users/{user_id}/GET, but we create: users/__TEMPLATE__/GET
    template_dir = test_client.tmp_path / base_path / "__TEMPLATE__" / method
    make_static_route(
        template_dir,
        headers={"Content-Type": "application/json"},
        body={"user_id": "template_matched", "message": "Found via template"},
    )

    response = test_client.get(f"/{base_path}/{user_id}")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "application/json"
    assert response.json() == {
        "user_id": "template_matched",
        "message": "Found via template",
    }


# === EDGE CASE TESTS ===


def test_directory_not_found(test_client: TestClient) -> None:
    """
    Test handler behavior when requested path doesn't exist and no template is available.

    WHY THIS TEST: This tests the FileNotFoundError path in get_handler() when
    _get_directory() returns None. This is a common scenario when users request
    non-existent endpoints.

    ALTERNATIVE APPROACHES:
    1. Return a custom 404 page instead of letting the exception bubble up
    2. Log the missing path for debugging purposes
    3. Provide a default fallback template mechanism

    This test ensures the server handles missing paths gracefully rather than crashing.
    """
    # Request a path that doesn't exist
    response = test_client.get("/nonexistent/path")

    # Should now return 404 due to improved error handling
    assert response.status_code == 404
    assert "Not Found" in response.text


@pytest.mark.parametrize("missing_file", ["STATUS", "DATA", "HEADERS"])
def test_missing_static_files(test_client: TestClient, missing_file: str) -> None:
    """
    Test handler behavior when static response files are missing.

    WHY THIS TEST: The _static_handler() method assumes STATUS, DATA, and HEADERS
    files exist. If any are missing, it will raise FileNotFoundError. This tests
    the robustness of our static file serving.

    ALTERNATIVE APPROACHES:
    1. Provide default values (STATUS=200, DATA=empty, HEADERS=empty)
    2. Use a validation step to ensure all required files exist
    3. Allow partial static definitions with sensible defaults

    This test exposes a fragility in the current implementation and suggests
    areas for improvement in error handling.
    """
    path = "incomplete"
    method = "GET"

    test_dir = test_client.tmp_path / path / method
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create all files except the one we're testing
    files_to_create = {
        "STATUS": "200",
        "DATA": "test",
        "HEADERS": "Content-Type: text/plain",
    }
    files_to_create.pop(missing_file)

    for filename, content in files_to_create.items():
        (test_dir / filename).write_text(content)

    response = test_client.get(f"/{path}")

    # Should return 404 due to missing file (FileNotFoundError)
    assert response.status_code == 404
    assert "Not Found" in response.text


def test_malformed_status_file(test_client: TestClient) -> None:
    """
    Test handler behavior when STATUS file contains non-integer content.

    WHY THIS TEST: The _static_handler() uses int() to parse the STATUS file.
    If it contains non-numeric content, ValueError will be raised. This tests
    input validation and error handling for malformed configuration.

    ALTERNATIVE APPROACHES:
    1. Use a default status code (200) if parsing fails
    2. Add validation with better error messages
    3. Support named status codes (e.g., "OK", "NOT_FOUND")

    This test highlights the need for more robust parsing and error handling.
    """
    path = "malformed_status"
    method = "GET"

    test_dir = test_client.tmp_path / path / method
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create files with malformed STATUS
    (test_dir / "STATUS").write_text("not_a_number")
    (test_dir / "DATA").write_text("test data")
    (test_dir / "HEADERS").write_text("Content-Type: text/plain")

    response = test_client.get(f"/{path}")

    # Should return 500 due to ValueError in int() conversion
    assert response.status_code == 500
    assert "Internal Server Error" in response.text


def test_non_executable_handle_script(test_client: TestClient) -> None:
    """
    Test handler behavior when HANDLE script exists but is not executable.

    WHY THIS TEST: The _dynamic_handler() checks os.access(handler, os.X_OK)
    and raises PermissionError if the script isn't executable. This is a common
    deployment issue where file permissions are incorrectly set.

    ALTERNATIVE APPROACHES:
    1. Attempt to make the script executable automatically
    2. Provide a clearer error message about permission issues
    3. Support HANDLE files that aren't scripts (e.g., simple text responses)

    This test ensures proper error handling for permission-related issues.
    """
    path = "non_executable"
    method = "GET"

    handler_dir = test_client.tmp_path / path / method
    handler_dir.mkdir(parents=True, exist_ok=True)

    # Create HANDLE script but don't make it executable
    handle_script = handler_dir / "HANDLE"
    handle_script.write_text("""#!/bin/sh
echo "response"
""")
    # Explicitly remove execute permissions
    handle_script.chmod(0o644)

    response = test_client.get(f"/{path}")

    # Should return 403 due to PermissionError
    assert response.status_code == 403
    assert "Forbidden" in response.text


def test_failing_handle_script(test_client: TestClient) -> None:
    """
    Test handler behavior when HANDLE script exits with non-zero code.

    WHY THIS TEST: The subprocess.run() call uses check=True, which raises
    CalledProcessError if the script exits with non-zero status. This tests
    error handling for scripts that fail during execution.

    ALTERNATIVE APPROACHES:
    1. Allow scripts to fail gracefully and return a default response
    2. Log the script error and return a 500 error page
    3. Provide retry mechanisms for transient failures

    This test ensures the server handles script failures appropriately.
    """
    path = "failing_script"
    method = "GET"

    handler_dir = test_client.tmp_path / path / method
    handler_dir.mkdir(parents=True, exist_ok=True)

    # Create HANDLE script that exits with error
    handle_script = handler_dir / "HANDLE"
    handle_script.write_text("""#!/bin/sh
echo "Script failed" >&2
exit 1
""")
    handle_script.chmod(0o755)

    response = test_client.get(f"/{path}")

    # Should return 500 due to CalledProcessError
    assert response.status_code == 500
    assert "Internal Server Error" in response.text


def test_handle_script_invalid_output(test_client: TestClient) -> None:
    """
    Test handler behavior when HANDLE script returns invalid/empty output.

    WHY THIS TEST: The _dynamic_handler() expects the script to output a path
    to a directory. If the output is empty or points to a non-existent location,
    the subsequent get_handler() call will fail.

    ALTERNATIVE APPROACHES:
    1. Validate script output before using it
    2. Provide default fallback behavior for invalid output
    3. Support relative paths more robustly

    This test exposes the fragility of trusting subprocess output directly.
    """
    path = "invalid_output"
    method = "GET"

    handler_dir = test_client.tmp_path / path / method
    handler_dir.mkdir(parents=True, exist_ok=True)

    # Create HANDLE script that outputs non-existent path
    handle_script = handler_dir / "HANDLE"
    handle_script.write_text("""#!/bin/sh
echo "/this/path/does/not/exist"
""")
    handle_script.chmod(0o755)

    response = test_client.get(f"/{path}")

    # Should return 404 because the output path doesn't exist (FileNotFoundError)
    assert response.status_code == 404
    assert "Not Found" in response.text


def test_empty_headers_file(test_client: TestClient) -> None:
    """
    Test handler behavior with empty HEADERS file.

    WHY THIS TEST: The _static_handler() splits headers by newlines and
    processes each line. An empty file should work without issues, but it's
    worth testing this edge case explicitly.

    ALTERNATIVE APPROACHES:
    1. Skip HEADERS file processing if it's empty
    2. Add default headers (like Content-Length) automatically
    3. Validate header format more strictly

    This test ensures empty headers don't break the response.
    """
    path = "empty_headers"
    method = "GET"

    test_dir = test_client.tmp_path / path / method
    make_static_route(
        test_dir,
        headers={},  # This will create an empty HEADERS file
        body="test content",
    )

    response = test_client.get(f"/{path}")

    assert response.status_code == 200
    assert response.json() == "test content"


def test_malformed_headers_file(test_client: TestClient) -> None:
    """
    Test handler behavior with malformed HEADERS file (no colon separators).

    WHY THIS TEST: The _static_handler() checks if ":" is in each header line
    before splitting. Lines without colons are silently ignored, which might
    mask configuration errors.

    ALTERNATIVE APPROACHES:
    1. Log warnings for malformed header lines
    2. Raise errors for invalid header format
    3. Support alternative header formats (e.g., space-separated)

    This test documents the current behavior of silently ignoring bad headers.
    """
    path = "malformed_headers"
    method = "GET"

    test_dir = test_client.tmp_path / path / method
    test_dir.mkdir(parents=True, exist_ok=True)

    (test_dir / "STATUS").write_text("200")
    (test_dir / "DATA").write_text("test content")
    # Create HEADERS file with lines that don't contain colons
    (test_dir / "HEADERS").write_text("InvalidHeaderLine\nAnotherBadLine")

    response = test_client.get(f"/{path}")

    # Should still work, but with no headers set
    assert response.status_code == 200
    assert response.text == "test content"
    # The malformed headers should be ignored


def test_root_path_handling(test_client: TestClient) -> None:
    """
    Test handler behavior for root path ("/").

    WHY THIS TEST: When path is "/", after stripping and splitting, we get an
    empty string. The handler constructs the method_dir as root_dir / "" / method.
    This tests whether empty path components are handled correctly.

    ALTERNATIVE APPROACHES:
    1. Treat root path specially (e.g., redirect to /index)
    2. Use a default path component for root requests
    3. Provide explicit root path handling

    This test ensures the root path works as expected within the current architecture.
    """
    method = "GET"

    # Create response for root path (empty string after stripping "/")
    test_dir = test_client.tmp_path / "" / method
    make_static_route(
        test_dir, headers={"Content-Type": "text/html"}, body="<h1>Root Page</h1>"
    )

    response = test_client.get("/")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "text/html"
    assert response.json() == "<h1>Root Page</h1>"


def test_handle_script_relative_path_output(test_client: TestClient) -> None:
    """
    Test HANDLE script that returns relative path (resolved against script location).

    WHY THIS TEST: The _dynamic_handler() has logic to handle relative paths
    from HANDLE scripts by resolving them against the script's parent directory.
    This tests that relative path resolution works correctly.

    ALTERNATIVE APPROACHES:
    1. Always require absolute paths from scripts
    2. Resolve relative paths against the server root instead
    3. Support multiple path resolution strategies

    This test validates the relative path resolution feature.
    """
    path = "relative_path"
    method = "GET"

    handler_dir = test_client.tmp_path / path / method
    handler_dir.mkdir(parents=True, exist_ok=True)

    # Create HANDLE script that returns relative path
    handle_script = handler_dir / "HANDLE"
    handle_script.write_text("""#!/bin/sh
echo "relative_response"
""")
    handle_script.chmod(0o755)

    # Create the response directory relative to the script
    response_dir = handler_dir / "relative_response"
    make_static_route(
        response_dir,
        headers={"Content-Type": "application/json"},
        body={"message": "Relative path resolved"},
    )

    response = test_client.get(f"/{path}")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "application/json"
    assert response.json() == {"message": "Relative path resolved"}


def test_deeply_nested_path(test_client: TestClient) -> None:
    """
    Test handler with deeply nested path components.

    WHY THIS TEST: This tests the robustness of path handling for complex
    URL structures. It ensures the handler can work with multiple path segments
    and construct appropriate directory structures.

    ALTERNATIVE APPROACHES:
    1. Limit path depth for security reasons
    2. Optimize path resolution for deep hierarchies
    3. Support path aliases or shortcuts

    This test validates that the handler works with realistic complex paths.
    """
    path = "api/v1/users/123/profile/settings"
    method = "GET"

    test_dir = test_client.tmp_path / path / method
    make_static_route(
        test_dir,
        headers={"Content-Type": "application/json"},
        body={"deeply": "nested", "path": "works"},
    )

    response = test_client.get(f"/{path}")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "application/json"
    assert response.json() == {"deeply": "nested", "path": "works"}


def test_template_fallback_chain(test_client: TestClient) -> None:
    """
    Test that template fallback works correctly through multiple path levels.

    WHY THIS TEST: The _get_directory() method iterates through path components
    to find __TEMPLATE__ directories. This tests the fallback mechanism works
    correctly for complex paths where templates might exist at different levels.

    ALTERNATIVE APPROACHES:
    1. Allow multiple templates per path level
    2. Support template inheritance/composition
    3. Provide template priority mechanisms

    This test validates the template resolution algorithm for complex scenarios.
    """
    # For path "users/123/profile" with method "GET", we want to test template replacement
    # The algorithm should find: users/__TEMPLATE__/profile/GET
    # where the "123" part gets replaced by "__TEMPLATE__"

    # Create a template that replaces the user ID: users/__TEMPLATE__/profile/GET
    template_dir = test_client.tmp_path / "users" / "__TEMPLATE__" / "profile" / "GET"
    make_static_route(
        template_dir,
        headers={"Content-Type": "application/json"},
        body={"template_level": "user_template", "fallback": "success"},
    )

    # Request a deeply nested path that should fall back to the template
    response = test_client.get("/users/123/profile")

    assert response.status_code == 200
    assert response.get_header("Content-Type") == "application/json"
    assert response.json() == {"template_level": "user_template", "fallback": "success"}
