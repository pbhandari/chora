"""
chora - A mock HTTP server that serves responses based on file system structure.
"""

from .server import start_server as serve

__all__ = ["serve"]
