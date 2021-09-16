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

from aiortsp.rtsp.parser import RTSPRequest
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

    def __init__(self, client: RTSPClientHandler, timeout: float = 60):
        self.client = client
        self.timeout = timeout
        self.session_id = generate_session_id()
        self.last_updated = time()

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
            self.client.server.streamer.play(self.session_id)
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
        # TRANSPORT {'transport': 'RTP', 'profile': 'AVP', 'protocol': 'TCP', 'delivery': 'unicast', 'interleaved': {'rtp': 0, 'rtcp': 1}}

        assert transport["transport"] == "RTP"
        assert transport["profile"] == "AVP"

        if transport["protocol"] == "TCP":
            assert "interleaved" in transport
            self.mode = "TCP"
            self.ports = transport["interleaved"]
        else:
            self.mode = "UDP"
            self.ports = transport["client_port"]
            # self.udp_ports = await asyncio.create_datagram_endpoint(

        transport["server_port"] = {"rtp": 4567, "rtcp": 4568}
        self.send_response(
            request=request,
            headers={"Transport": RTPTransport.build_transport_string([transport])},
        )

        stream_id = self.client.server.streamer.setup_stream(
            self.session_id, request.request_url
        )

        clients = self.client.server.streamer.clients.setdefault(stream_id, [])
        clients.append((self.handle_rtp, self.handle_rtcp))

    def handle_rtp(self, pkt):
        print("RTP", pkt)
        self.client.send_binary(0, bytes(pkt))

    def handle_rtcp(self, pkt):
        print("RTCP")
