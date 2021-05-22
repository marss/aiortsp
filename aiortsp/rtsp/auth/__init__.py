"""
RTSP Authentication module.
---------------------------

Implements Basic and Digest authentication.
"""

from .basic import BasicClientAuth
from .digest import DigestClientAuth
from .server import ServerAuth

__all__ = ["BasicClientAuth", "DigestClientAuth", "ServerAuth"]
