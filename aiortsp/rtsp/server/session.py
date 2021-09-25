"""
Session module
==============

When a client SETUP a new session, a session object is created.
"""
from __future__ import annotations

import random
import string
from time import time
from typing import TYPE_CHECKING

from aiortsp.rtp import RTP
from aiortsp.rtsp.parser import RTSPRequest
from aiortsp.rtsp.server.transport.base import ServerTransport
from aiortsp.transport.base import RTPTransport

if TYPE_CHECKING:
    from .base import RTSPClientHandler


def generate_session_id(length: int = 10) -> str:
    """
    Generate a unique session identifier
    """
    return "".join(
        [random.choice(string.ascii_lowercase + string.digits) for _ in range(length)]
    )


class MediaSession:
    """
    Object handling server side session
    """

    def __init__(
        self, client: RTSPClientHandler, transport: ServerTransport, timeout: float = 60
    ):
        self.transport = transport
        self.client = client
        self.timeout = timeout
        self.session_id = generate_session_id()
        self.last_updated = time()
        self.stream_id = None

    @property
    def streamer(self):
        return self.client.server.streamer

    def close(self):
        self.transport.close()
        clients = self.streamer.clients[self.stream_id]
        clients.remove(self.handle_rtp)

    def send_response(
        self,
        request: RTSPRequest,
        code: int = 200,
        msg: str = "OK",
        headers: dict = None,
    ):
        """
        Send a response using underlying client.

        Injects session information in the response.
        """
        self.client.send_response(
            request=request,
            code=code,
            msg=msg,
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
        self.last_updated = time()
        req_type = req.method

        # Some request types are just for polling / pinging.
        if req_type == "OPTIONS":
            self.client.handle_options(req)

        elif req_type == "PLAY":
            # TODO: do something better than that
            self.streamer.play(self.session_id)
            self.send_response(request=req)

        else:
            self.send_response(
                request=req, code=400, msg=f"invalid request on session: {req_type}"
            )

    def handle_session(self, request: RTSPRequest, transport: dict):
        """
        Handle the life cycle of a streaming session
        """
        self.send_response(
            request=request,
            headers={"Transport": RTPTransport.build_transport_string([transport])},
        )

        self.stream_id = self.streamer.setup_stream(
            self.session_id, request.request_url
        )

        clients = self.streamer.clients.setdefault(self.stream_id, [])
        clients.append(self.handle_rtp)

    def handle_rtp(self, rtp: RTP):
        self.transport.send_rtp(rtp)
