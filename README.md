# chora

> **Warning:** chora is intended for development and testing only. Do not use
this server in production environments.  If you _do_ use this in production, and
get your ass handed to you, please don't come crying to me.

chora is a mock HTTP server for Python that serves responses based on your file
system structure. It's designed for testing and development, allowing you to
quickly simulate APIs or static content by simply organizing files and
directories.

## Features

- File-based routing: Map HTTP endpoints to files and folders.
- Supports multiple HTTP methods: Serve different responses for GET, POST, etc., using file naming conventions.
- Easy to configure: No code changes needed—just update the file system.
- Great for testing: Quickly mock APIs for frontend or integration tests.

## How It Works

- Each directory represents a route.
- Files inside directories represent responses, statuses, and headers for specific HTTP methods and endpoints.
- Dynamic request handling is done with a special HANDLE script.
- The server reads the file system to determine how to respond to incoming requests.

### Example Structure

```text
example/
├── users/
│   └── GET/
│   │    ├── HEADERS                  # Custom headers for GET /users
│   │    ├── DATA                     # Response body for GET /users
│   │    └── STATUS                   # HTTP status code for GET /users
│   └── POST/
│   │    ├── HEADERS                  # Custom headers for POST /users/
│   │    ├── DATA                     # Response body for POST /users/
│   │    └── STATUS                   # HTTP status code for POST /users/
│   └── PUT/
│        └── HANDLE                   # Custom handler for PUT /users/
└── status/
    └── POST/
        ├── HEADERS                   # Custom headers for POST /status
        ├── DATA                      # Response body for POST /status
        └── STATUS                    # HTTP status code for POST /status
```

A request to GET /users will return the contents of users/GET/DATA, with
headers from users/GET/HEADERS and status from users/GET/STATUS.

A request to PUT /users will execute the HANDLE script, with $1 containing the folder
with the details of the request.  The script is expected to introspect that and supply
a path to a folder containing the DATA, HEADERS and STATUS files.

## Installation

pip install chora

## Usage

chora --root ./example --port 8080

- --root: Path to the directory containing your mock API structure.
- --port: Port to run the server on (default: 8000).

## Customization

- Add new endpoints by creating directories and files.
- Use subdirectories for nested routes.

## License

MIT

## Author

pbhandari (<pbhandari@pbhandari.ca>)

For more information, see the project homepage: <https://github.com/pbhandari/chora>
