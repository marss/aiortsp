"""
Implementation of an RTSP Server mechanism

This is indented to remain low level,
and excludes any media treatment.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Dict, List, Optional
from urllib.parse import urlparse

from aiortsp.rtsp.auth.server import ServerAuth
from aiortsp.rtsp.connection import USER_AGENT, RTSPEndpoint
from aiortsp.rtsp.parser import RTSPRequest
from aiortsp.rtsp.server.transport.tcp import TCPServerTransport
from aiortsp.rtsp.server.transport.udp import UDPServerTransport
from aiortsp.transport.base import RTPTransport

from .session import MediaSession
from .streamer import RTPStreamer, StreamNotFound

_logger = logging.getLogger("rtsp_server")


class RTSPClientHandler(RTSPEndpoint):
    """
    RTSP Client handler: handles the server side of a client connection.
    """

    def __init__(self, server, timeout: float = 10):
        super().__init__(server.logger, timeout)
        self.server = server
        self.authenticator = server.get_authenticator()
        self._supported_requests = {
            "OPTIONS": self.handle_options,
            "DESCRIBE": self.handle_describe,
            "SETUP": self.handle_setup,
            "TEARDOWN": self.handle_teardown,
            # "GET_PARAMETER": self.handle_get_parameter,
        }
        self.sessions: Dict[str, MediaSession] = {}
        self.binary_indexes = set()

    def identify_us(self, headers: dict):
        """Identifying the server"""
        headers["Server"] = USER_AGENT

    def connection_made(self, transport):
        """New client connected"""
        super().connection_made(transport)
        self.logger.info("connection made from %s", self.peer_name)

    def data_received(self, data):
        """Called when some data is received.

        The argument is a bytes object.
        """
        for msg in self.parser.parse(data):  # type: RTSPRequest
            if msg.type != "request":
                self.logger.warning("dropping unsupported msg: %s", msg)
                continue

            self.logger.info("got request: %s", msg)

            session_id = msg.get_session()

            if session_id is not None:
                # A session is provided.
                # Session means authent.
                if not self.check_auth(msg):
                    continue

                # Check if session exists
                if session_id not in self.sessions:
                    self.send_response(request=msg, code=400, msg="invalid session")
                    continue

                session = self.sessions[session_id]

                session.handle_request(msg)

            else:
                if msg.method not in self._supported_requests:
                    self.logger.warning(
                        "unsupported request type %s: %s", msg.method, msg
                    )
                    self.send_response(msg, 405, "Method Not Allowed")
                    continue

                self._supported_requests[msg.method](msg)

    def connection_lost(self, exc):
        """Called when the connection is lost or closed.

        The argument is an exception object or None (the latter
        meaning a regular EOF is received or the connection was
        aborted or closed).
        """
        self.logger.info("connection lost from %s", self.peer_name)

        for session_id, session in self.sessions.items():
            self.logger.info("closing session %s", session_id)
            session.close()

    def check_auth(self, request: RTSPRequest) -> bool:
        """
        Check authentication from client request.

        :param request: request from client
        :return: True if authentication was successful,
                 False otherwise and response is sent.
        """
        return self.authenticator.handle_auth(self, request)

    # --- RTSP Request handlers ---

    def handle_options(self, req: RTSPRequest):
        """Respond to OPTIONS request"""

        self.send_response(
            request=req,
            code=200,
            msg="OK",
            headers={"Public": ", ".join(self._supported_requests.keys())},
        )

    def handle_describe(self, req: RTSPRequest):
        """Respond to DESCRIBE request"""
        self.logger.info("requesting description for path %s", req.request_url)

        if not self.check_auth(req):
            return

        # TODO Check for 'Accept' field containing 'application/sdp'.
        # If not, just assume SDP.

        try:
            content_type, description = self.server.streamer.describe(req.request_url)

            self.send_response(
                request=req,
                code=200,
                msg="OK",
                headers={"Content-Type": content_type},
                body=description.encode(),
            )

        except StreamNotFound:
            self.send_response(request=req, code=404, msg="Stream not found")

    def handle_setup(self, req: RTSPRequest):
        """Respond to SETUP request"""

        if not self.check_auth(req):
            return

        # Client MAY try to re-setup, but unless we plan to support this,
        # we must politely decline with a 455 error
        if "session" in req.headers:
            self.send_response(
                request=req, code=455, msg="Method Not Valid in This State"
            )
            return

        # Parse Transport header, which contains all we need.
        if "transport" not in req.headers:
            self.send_response(request=req, code=400, msg="invalid request")
            return

        transports = RTPTransport.parse_transport_fields(req.headers["transport"])
        self.logger.info("transports requested: %s", transports)

        # Try to find a matching transport.
        server_transport = None
        while transports:
            transport = transports.pop(0)

            trans_type = tuple(
                transport.get(k)
                for k in ["transport", "profile", "protocol", "delivery"]
            )

            if trans_type == ("RTP", "AVP", "UDP", "multicast"):
                # TODO Support this case soon
                self.logger.info("requesting multicast transport")
                # self.server.streamer.get_multicast_addr(req.request_url)
                continue

            if trans_type == ("RTP", "AVP", "UDP", "unicast"):
                self.logger.info("requesting UDP unicast")
                ports = transport["client_port"]
                server_transport = UDPServerTransport(
                    self, self.peer_name[0], ports["rtp"], ports["rtcp"]
                )
                transport["server_port"] = {
                    "rtp": server_transport.rtp_port,
                    "rtcp": server_transport.rtcp_port,
                }
                break

            if trans_type == ("RTP", "AVP", "TCP", "unicast"):
                self.logger.info("requesting TCP streaming")
                assert "interleaved" in transport
                ports = transport["interleaved"]
                server_transport = TCPServerTransport(self, ports["rtp"], ports["rtcp"])
                break

            self.logger.info("skipping unsupported transport %s", trans_type)

        if not server_transport:
            # TODO Send a proper reply; for now just reject
            self.send_response(request=req, code=400, msg="invalid request")
            return

        # Build transport / session
        session = MediaSession(self, server_transport)
        session.handle_session(req, transport)
        self.sessions[session.session_id] = session

    def handle_teardown(self, req: RTSPRequest):
        """
        Handle a TEARDOWN request.

        This requires an active session, which will be destroyed
        """
        session_id = req.get_session()

        if session_id not in self.sessions:
            self.send_response(request=req, code=400, msg="invalid request")
            return

        # TODO: perform a real teardown of the session
        # session = self.sessions[session_id]
        # session.teardown()

        self.logger.info("removing session %s", session_id)
        del self.sessions[session_id]

        self.send_response(request=req, code=200, msg="OK")


class RTSPServer:
    """
    Create an RTSP Server providing streams to be served to clients
    """

    def __init__(
        self,
        streamer: RTPStreamer,
        host: str = "0.0.0.0",
        port: int = 554,
        users: Optional[Dict[str, str]] = None,
        accept_auth: List[str] = None,
        logger: logging.Logger = None,
        timeout: float = 10,
    ):
        self.host = host
        self.port = port
        self.users = users or {}
        self.accept_auth = (
            [auth.lower() for auth in accept_auth]
            if accept_auth
            else ["basic", "digest"]
        )
        self.default_timeout = timeout
        self.logger = logger or _logger
        self._server = None
        self.streamer = streamer

    def get_authenticator(self) -> ServerAuth:
        """
        Create an authenticator instance for a client
        """
        return ServerAuth(credentials=self.users, protocols=self.accept_auth)

    async def start(self):
        """
        Start the RTSP Server.
        """
        self.logger.info("start serving on rtsp://%s:%s/", self.host, self.port)
        self._server = await asyncio.get_event_loop().create_server(
            lambda: RTSPClientHandler(self),
            host=self.host,
            port=self.port,
            family=socket.AF_INET,
        )

    async def stop(self):
        """Stop RTSP server"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def run(self):
        async with self:
            await self._server.wait_closed()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
