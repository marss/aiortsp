"""
Basic authentication support
"""
from base64 import b64encode

from .base import ClientAuth


class BasicClientAuth(ClientAuth):
    """
    Implementation of Basic authentication
    """

    def __init__(self, username, password, max_retry=1):
        super().__init__(max_retry)
        self.username = username
        self.password = password

    def make_auth(self, method, url, headers):
        b64 = b64encode(f'{self.username}:{self.password}'.encode())
        headers['Authorization'] = f'Basic {b64.decode()}'
