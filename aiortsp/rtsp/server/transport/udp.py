from aiortsp.rtcp import RTCP
from aiortsp.rtp import RTP
from aiortsp.transport.udp import UDPTransport

from .base import ServerTransport


class UDPServerTransport(ServerTransport):
    """
    TCP transport using the main RTSP socket
    """

    def __init__(self, connection, address: str, rtp_port: int, rtcp_port: int):
        super().__init__(connection)

        self.rtp_sock, self.rtcp_sock = UDPTransport.get_socket_pair()
        self.rtp_sock.connect((address, rtp_port))
        self.rtcp_sock.connect((address, rtcp_port))

    @property
    def rtp_port(self) -> int:
        return self.rtp_sock.getsockname()[1]

    @property
    def rtcp_port(self) -> int:
        return self.rtcp_sock.getsockname()[1]

    def _send_rtp(self, rtp: RTP):
        self.rtp_sock.send(bytes(rtp))

    def _send_rtcp(self, rtcp: RTCP):
        self.rtcp_sock.send(bytes(rtcp))

    def close(self):
        self.rtp_sock.close()
        self.rtcp_sock.close()
        self.connection = None
