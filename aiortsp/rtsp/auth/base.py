"""
Base classes for authentication methods
"""
from abc import ABC, abstractmethod

from aiortsp.rtsp.parser import RTSPRequest


class ResponseSender(ABC):
    """
    Stub for sending responses to clients
    """

    @abstractmethod
    def send_response(
        self,
        request: RTSPRequest,
        code: int = 200,
        msg: str = "OK",
        headers: dict = None,
        body: bytes = None,
    ):
        """
        Send a response to a client
        """


class ClientAuth:
    """
    Base class for client authentication
    """

    def __init__(self, max_retry=1):
        self.max_retry = max_retry
        self.retry_count = 0

    def handle_ok(self, headers: dict):  # pylint: disable=unused-argument
        """
        A response was successful with this authentication. Reset retry count
        """
        self.retry_count = 0

    def handle_401(self, headers: dict):  # pylint: disable=unused-argument
        """
        :returns True if retry is allowed
        """
        self.retry_count += 1
        return self.retry_count <= self.max_retry

    def make_auth(self, method: str, url: str, headers: dict):
        """
        Add Authorization to the headers of given request

        Method and URL can be used by some implementations (digest)
        to generate the authorization header.

        :param method: RTSP method being called
        :param url: RTSP URL being used for the method call
        :param headers: Headers dict where to add authorization
        """
        raise NotImplementedError  # pragma: no cover
