"""
Implementation of an RTSP Server mechanism

This is indented to remain low level,
and excludes any media treatment.
"""

from urllib.parse import urlparse

import asyncio
import logging
import socket
from typing import List, Optional, Dict

from aiortsp.rtp import RTP
from aiortsp.rtsp.connection import RTSPEndpoint, USER_AGENT
from aiortsp.rtsp.parser import RTSPRequest

_logger = logging.getLogger('rtsp_server')


class RTSPClientHandler(RTSPEndpoint):
    """
    RTSP Client handler: handles the server side of a client connection.
    """

    def __init__(self, server, timeout: float = 10):
        super().__init__(server.logger, timeout)
        self.server = server
        self.authenticated = False
        self._client = None
        self._supported_requests = {
            'OPTIONS': self.handle_options,
            'DESCRIBE': self.handle_describe,
            'SETUP': self.handle_setup,
        }

    def identify_us(self, headers: dict):
        """Identifying the server"""
        headers['Server'] = USER_AGENT

    def connection_made(self, transport):
        """New client connected"""
        self._client = transport.get_extra_info('peername')
        self.logger.info('connection made from %s', self._client)
        super().connection_made(transport)

    def data_received(self, data):
        """Called when some data is received.

        The argument is a bytes object.
        """
        for msg in self.parser.parse(data):  # type: RTSPRequest
            if msg.type != 'request':
                self.logger.warning('dropping unsupported msg: %s', msg)
                continue

            if msg.method not in self._supported_requests:
                # TODO Answer something nice
                self.logger.warning('unsupported request type %s: %s', msg.method, msg)
                self.send_response(msg, 405, 'Method Not Allowed')
                continue

            self.logger.info('got request: %s', msg)
            self._supported_requests[msg.method](msg)
            # TODO Error handling

    def connection_lost(self, exc):
        """Called when the connection is lost or closed.

        The argument is an exception object or None (the latter
        meaning a regular EOF is received or the connection was
        aborted or closed).
        """
        self.logger.info('connection lost from %s', self._client)

    def pause_writing(self):
        """
        Called when the transport's buffer goes over the high-water mark.
        """

    def resume_writing(self):
        """
        Called when the transport's buffer drains below the low-water mark.
        """

    def check_auth(self, request: RTSPRequest) -> bool:
        """
        Check authentication from client request.

        :param request: request from client
        :return: True if authentication was successful,
                 False otherwise and response is sent.
        """
        if self.server.password and not self.authenticated:
            self.send_response(request, 401, 'Unauthorized', headers={
                'WWW-Authenticate': 'Basic realm="aiortsp"'
            })
            return False

        return True

    # --- RTSP Request handlers ---

    def handle_options(self, req: RTSPRequest):
        """Respond to OPTIONS request"""
        self.send_response(request=req, code=200, msg='OK', headers={
            'Public': ', '.join(self._supported_requests.keys())
        })

    def handle_describe(self, req: RTSPRequest):
        """Respond to DESCRIBE request"""
        self.logger.info('requesting description for path %s', req.request_url)

        if not self.check_auth(req):
            return

        description = self.server.describe(req.request_url)

        if description:
            self.send_response(request=req, code=200, msg='OK', headers={
                'Content-Type': 'application/sdp'
            }, body=description.encode())
        else:
            self.send_response(request=req, code=404, msg='NOT FOUND')

    def handle_setup(self, req: RTSPRequest):
        """Respond to SETUP request"""


class RTPStreamer:
    """
    RTP Stream to be served by the server
    """

    def __init__(self):
        self.clients = set()

    def inject(self, pkt: RTP):
        """
        Inject an RTP packet
        """

    def to_sdp(self, url) -> str:
        """
        Build an SDP message for this stream
        """
        raise NotImplementedError


class RTSPServer:
    """
    Create an RTSP Server providing streams to be served to clients
    """

    def __init__(
            self,
            host: str = '0.0.0.0',
            port: int = 554,
            users: Optional[Dict[str, str]] = None,
            accept_auth: List[str] = None,
            logger: logging.Logger = None,
            timeout: float = 10
    ):
        self.host = host
        self.port = port
        self.users = users
        self.accept_auth = [auth.lower() for auth in accept_auth] if accept_auth else ['basic', 'digest']
        self.default_timeout = timeout
        self.logger = logger or _logger
        self._server = None
        self.streamers: Dict[str, RTPStreamer] = {}

    async def start(self):
        """
        Start the RTSP Server.
        """
        self.logger.info('start serving on rtsp://%s:%s/', self.host, self.port)
        self._server = await asyncio.get_event_loop().create_server(
            lambda: RTSPClientHandler(self),
            host=self.host,
            port=self.port,
            family=socket.AF_INET
        )

    async def stop(self):
        """Stop RTSP server"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def register_streamer(self, path: str, streamer: RTPStreamer):
        """
        Register a streamer object at given URL path.

        The streamer object is the responder for everything related to a stream.
        """
        self.streamers[path] = streamer

    def unregister_streamer(self, path: str):
        """
        Unregister a streamer.

        Not sure this will ever be used, but worth having for completeness.

        :param path: Path the streamer was registered to
        """
        del self.streamers[path]

    def describe(self, url) -> Optional[str]:
        """
        Return SDP description of a registered stream, if found.
        """
        p_url = urlparse(url)
        if p_url.path in self.streamers:
            return self.streamers[p_url.path].to_sdp(p_url)

        return None
