"""
TCP Interleaved transport.
"""
import logging

from aiortsp.rtcp.parser import RTCP
from aiortsp.rtsp.errors import RTSPError
from aiortsp.rtsp.parser import RTSPBinary
from .base import RTPTransport

_logger = logging.getLogger('rtp.session')

DEFAULT_BUFFER_SIZE = 4 * 1024 * 1024


class TCPTransport(RTPTransport):
    """
    TCP Transport.
    --------------

    Uses connection directly
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_number = kwargs.pop('stream_number', 2)
        self.rtp_idx = []
        self.rtcp_idx = []

        self.receive_buffer = kwargs.get('receive_buffer', DEFAULT_BUFFER_SIZE)
        self.send_buffer = kwargs.get('send_buffer', DEFAULT_BUFFER_SIZE)

    async def prepare(self):
        """
        Register handlers for each stream. Assume each stream has one RTP and one RTCP channel.
        """

        for _ in range(self.stream_number):
            rtp = self.connection.register_binary_handler(self.handle_rtp_bin)
            rtcp = self.connection.register_binary_handler(self.handle_rtcp_bin)
            self.rtp_idx.append(rtp)
            self.rtcp_idx.append(rtcp)
            self.logger.info('receiving interleaved RTP (%s) and RTCP (%s)', rtp, rtcp)

    @property
    def running(self) -> bool:
        """
        True if both RTP and RTCP sinks are running.
        """
        return self.connection.running

    def close(self, error=None):
        """
        Perform cleanup, which by default is closing both sinks.
        """
        super().close(error)
        self.connection.close()

    def handle_rtcp_bin(self, binary: RTSPBinary):
        """
        Handle interleaved data registered as RTCP
        """
        self.handle_rtcp_data(binary.data)

    def handle_rtp_bin(self, binary: RTSPBinary):
        """
        Handle interleaved data registered as RTP
        """
        self.handle_rtp_data(binary.data)

    def on_transport_request(self, headers: dict, stream_number=0):
        import pdb;pdb.set_trace();
        if stream_number < 0 or stream_number >= len(self.rtp_idx):
            raise ValueError("Invalid stream number")
        rtp_idx = self.rtp_idx[stream_number]
        rtcp_idx = self.rtcp_idx[stream_number]
        headers['Transport'] = f'RTP/AVP/TCP;unicast;interleaved={rtp_idx}-{rtcp_idx}'

    def on_transport_response(self, headers: dict, stream_number=0):
        if 'transport' not in headers:
            raise RTSPError('error on SETUP: Transport not found')

        rtp_idx = self.rtp_idx[stream_number]
        rtcp_idx = self.rtcp_idx[stream_number]
        interleaved = f'{rtp_idx}-{rtcp_idx}'

        fields = self.parse_transport_fields(headers['transport'])
        if fields.get('interleaved') != interleaved:
            raise RTSPError(f'Invalid returned interleaved header: expected {interleaved}, got {fields.get("interleaved")}')


    def send_rtcp_report(self, rtcp: RTCP, stream_index=0):
        """
        Send an RTCP report back to the server for a specific stream.
        """
        if stream_index < 0 or stream_index >= len(self.rtcp_idx):
            self.logger.error("Invalid stream index")
            return

        rtcp_channel = self.rtcp_idx[stream_index]
        self.connection.send_binary(rtcp_channel, bytes(rtcp))

