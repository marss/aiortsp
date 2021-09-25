"""
Server side transport

Receives RTP packets from the original source to be transmitted
back to client. Should also build RTCP packets for sending statistics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from aiortsp.rtcp import RTCP
from aiortsp.rtp import RTP

if TYPE_CHECKING:
    from aiortsp.rtsp.server.base import RTSPClientHandler


class ServerTransport(ABC):
    def __init__(self, connection: RTSPClientHandler) -> None:
        self.connection = connection

    def send_rtp(self, rtp: RTP):
        """
        Getting an RTP frame: count it and send to underlying
        """
        # TODO stats and RTCP generation
        self._send_rtp(rtp)

    @abstractmethod
    def _send_rtp(self, rtp: RTP):
        """Internal implementation of sending RTP to client"""

    @abstractmethod
    def _send_rtcp(self, rtcp: RTCP):
        """Internal implementation of sending RTCP to client"""
