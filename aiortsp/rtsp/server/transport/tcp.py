from aiortsp.rtcp import RTCP
from aiortsp.rtp import RTP

from .base import ServerTransport


class TCPServerTransport(ServerTransport):
    """
    TCP transport using the main RTSP socket
    """

    def __init__(self, connection, rtp_idx: int, rtcp_idx: int) -> None:
        super().__init__(connection)

        self.rtp_idx = rtp_idx
        assert rtp_idx not in connection.binary_indexes
        connection.binary_indexes.add(rtp_idx)

        self.rtcp_idx = rtcp_idx
        assert rtcp_idx not in connection.binary_indexes
        connection.binary_indexes.add(rtcp_idx)

    def _send_rtp(self, rtp: RTP):
        self.connection.send_binary(self.rtp_idx, bytes(rtp))

    def _send_rtcp(self, rtcp: RTCP):
        self.connection.send_binary(self.rtcp_idx, bytes(rtcp))

    def close(self):
        self.connection.binary_indexes.remove(self.rtp_idx)
        self.connection.binary_indexes.remove(self.rtcp_idx)
        self.connection = None
