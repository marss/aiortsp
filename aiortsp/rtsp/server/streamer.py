"""
RTP Streamer
============

Base class for handling RTP media and requests from clients
"""
from abc import ABC, abstractmethod
from typing import List, Tuple

from aiortsp.rtcp import RTCP
from aiortsp.rtp import RTP


class StreamerError(Exception):
    """Base error for streamer issues"""


class StreamNotFound(StreamerError):
    """Requested stream not found"""


class RTPStreamer(ABC):
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
        self.clients = {}

    def send_rtp(self, stream_id: str, pkt: RTP):
        """
        Send an RTP packet for provided stream id.
        """
        clients = self.clients.get(stream_id, [])
        for cb, _ in clients:
            cb(pkt)

    def send_rtcp(self, stream_id: str, pkt: RTCP):
        """
        Send an RTCP packet for provided stream id.
        """
        clients = self.clients.get(stream_id, [])
        for _, cb in clients:
            cb(pkt)

    @abstractmethod
    def describe(self, url: str, accept: List[str] = None) -> Tuple[str, str]:
        """
        Called upon DESCRIBE request.

        When no accept is provided, assuming SDP.

        Given the requested URL, implementer must
        build an SDP response (or other format if supported)
        to be streamed out.

        :param url: requested URL to be described
        :param accept: A list of supported formats
        :returns: format, data
        :raises StreamNotFound: when the URL is not supported
        """

    @abstractmethod
    def setup_stream(self, session_id: str, setup_url: str) -> str:
        """
        Inform streamer of a client requesting to setup a particular stream.

        A session id is provided, opaque from the streamer point of view,
        but should be used to related streams setup for a particular session;
        a client could for example request video and sound on the same session.

        The streamer implementation can take its time to perform preparation.
        All it has to do is return without error for the setup to be accepted.

        If accepted, the streamer MUST return a string which will be associated
        with this stream, when sending RTP or RTCP packets.

        :param session_id: opaque session id related to this request
        :param setup_url: defines the media to be played back.
        :returns: a string identifying this stream.
        """

    @abstractmethod
    def play(
        self,
        session_id: str,
        since: float = None,
        until: float = None,
        speed: float = 1,
    ):
        """
        Handle the client requesting to start playing streams for a session.

        :param session_id: session to start playing
        :param since: timestamp to start playing video. Now if not provided.
        :param until: timestamp until which to play. Forever if not provided.
        :param speed: playing speed, with 1 as realtime
        """

    @abstractmethod
    def pause(self, session_id: str):
        """
        Put a session in pause.

        :param session_id: session to pause
        """

    @abstractmethod
    def teardown(self, session_id: str):
        """
        Close any ressources associated to a session.

        After this, the session_id must be considered as dead,
        and all resources associated can be freed.

        :param session_id: session to teardown
        """
