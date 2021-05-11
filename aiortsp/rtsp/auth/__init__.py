"""
RTSP Authentication module.
---------------------------

Implements Basic and Digest authentication.
"""

from .basic import BasicClientAuth
from .digest import DigestClientAuth

__all__ = ['BasicClientAuth', 'DigestClientAuth']
