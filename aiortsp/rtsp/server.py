"""
Implementation of an RTSP Server mechanism

This is indented to remain low level,
and excludes any media treatment.
"""
from __future__ import annotations

import asyncio
import logging
import random
import socket
import string
from time import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from aiortsp.rtp import RTP
from aiortsp.rtsp.auth.server import ServerAuth
from aiortsp.rtsp.connection import USER_AGENT, RTSPEndpoint
from aiortsp.rtsp.parser import RTSPRequest
from aiortsp.transport.base import RTPTransport

_logger = logging.getLogger("rtsp_server")


class ServerSession:
    """
    Object handling server side session
    """

    def __init__(self, client: RTSPClientHandler, timeout: float = 60):
        self.client = client
        self.timeout = timeout
        self.session_id = self.generate_session_id()
        self.last_updated = time()

    def generate_session_id(self) -> str:
        """
        Generate a unique session identifier
        """
        return "".join(
            [random.choice(string.ascii_lowercase + string.digits) for _ in range(10)]
        )

    def send_response(
        self,
        request: RTSPRequest,
        msg: str = "OK",
        code: int = 200,
        headers: dict = None,
    ):
        self.client.send_response(
            request=request,
            msg=msg,
            code=code,
            headers={
                **{"Session": f"{self.session_id};timeout={self.timeout}"},
                **(headers or {}),
            },
        )

    def handle_request(self, req: RTSPRequest):
        """
        A request for this session is received
        """
        # First of all, just refresh the timer
        self.ts = time()
        req_type = req.method

        # Some request types are just for polling / pinging.
        if req_type == "OPTIONS":
            self.client.handle_options(req)

        elif req_type == "PLAY":
            # TODO: do something better than that
            self.send_response(request=req)

        else:
            self.send_response(
                request=req, code=400, msg=f"invalid request on session: {req_type}"
            )

    async def handle_session(self, request: RTSPRequest, transport: dict):
        """
        Handle the life cycle of a streaming session
        """
        # 1 - Prepare the streaming output
        # for now let's just hardcode some fake ports
        transport["server_port"] = {"rtp": 4567, "rtcp": 4568}
        self.send_response(
            request=request,
            headers={"Transport": RTPTransport.build_transport_string([transport])},
        )


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
            "OPTIONS": self.handle_options,
            "DESCRIBE": self.handle_describe,
            "SETUP": self.handle_setup,
            "TEARDOWN": self.handle_teardown,
            # "GET_PARAMETER": self.handle_get_parameter,
        }
        self.sessions: Dict[str, ServerSession] = {}

    def identify_us(self, headers: dict):
        """Identifying the server"""
        headers["Server"] = USER_AGENT

    def connection_made(self, transport):
        """New client connected"""
        self._client = transport.get_extra_info("peername")
        self.logger.info("connection made from %s", self._client)
        super().connection_made(transport)

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
        self.logger.info("connection lost from %s", self._client)

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
        if self.server.auth_server:
            return self.server.auth_server.handle_auth(self, request)
        return True

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

        description = self.server.describe(req.request_url)

        if description:
            self.send_response(
                request=req,
                code=200,
                msg="OK",
                headers={"Content-Type": "application/sdp"},
                body=description.encode(),
            )
        else:
            self.send_response(request=req, code=404, msg="NOT FOUND")

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

        while transports:
            transport = transports[0]
            transports.remove(transport)

            if transport["protocol"] != "UDP":
                # TODO Support this case soon
                continue

            if transport["delivery"] != "unicast":
                # TODO add support for multicast
                continue

            # found it!
            break

        if not transport:
            # TODO Send a proper reply; for now just reject
            self.send_response(request=req, code=400, msg="invalid request")
            return

        # Build transport / session
        session = ServerSession(self)
        asyncio.create_task(session.handle_session(req, transport))
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


class RTPStreamer:
    """
    RTP Streamer class
    ==================

    This is a base class for implementing RTP
    session handling. It can be used in many ways:

    - Starting to play back local files
    - Starting a streaming session from an ongoing stream
    - Streaming on demand
    - Implementing an RTSP gateway to a non-rtsp VDR?
    - Proxying
    - ...
    """

    def __init__(self):
        self.clients = set()

    def inject(self, pkt: RTP):
        """
        Inject an RTP packet
        """

    def to_sdp(self, url) -> str:
        """
        Called upon DESCRIBE request.

        Given the requested URL, implementer must
        build an SDP object describing the content
        to be streamed out.

        TODO Should the output be the SDP string,
        or an SDP object?
        """
        raise NotImplementedError


class RTSPServer:
    """
    Create an RTSP Server providing streams to be served to clients
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 554,
        users: Optional[Dict[str, str]] = None,
        accept_auth: List[str] = None,
        logger: logging.Logger = None,
        timeout: float = 10,
    ):
        self.host = host
        self.port = port
        self.users = users
        accept_auth = (
            [auth.lower() for auth in accept_auth]
            if accept_auth
            else ["basic", "digest"]
        )
        if users:
            self.auth_server = ServerAuth(credentials=users, protocols=accept_auth)
        else:
            self.auth_server = None
        self.default_timeout = timeout
        self.logger = logger or _logger
        self._server = None
        self.streamers: Dict[str, RTPStreamer] = {}

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
