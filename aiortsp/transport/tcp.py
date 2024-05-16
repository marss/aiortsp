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
        self.rtp_idx = [None] * self.num_streams
        self.rtcp_idx = [None] * self.num_streams

        self.receive_buffer = kwargs.get('receive_buffer', DEFAULT_BUFFER_SIZE)
        self.send_buffer = kwargs.get('send_buffer', DEFAULT_BUFFER_SIZE)

    async def prepare(self):
        """
        Register handlers for each stream. Assume each stream has one RTP and one RTCP channel.
        """

        for idx in range(self.num_streams):
            rtp = self.connection.register_binary_handler(self.handle_rtp_bin)
            rtcp = self.connection.register_binary_handler(self.handle_rtcp_bin)
            self.rtp_idx[idx] = rtp
            self.rtcp_idx[idx] = rtcp
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
        channel_number = binary.id//2
        self.handle_rtcp_data(binary.data, channel_number)

    def handle_rtp_bin(self, binary: RTSPBinary):
        """
        Handle interleaved data registered as RTP
        """
        channel_number = binary.id//2
        self.handle_rtp_data(binary.data, channel_number)

    def on_transport_request(self, headers: dict, stream_number=0):
        if stream_number not in range(self.num_streams):
            raise ValueError(f"Invalid stream number {stream_number}")
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


    async def send_rtcp_report(self, rtcp: RTCP, stream_number=0):
        """
        Send an RTCP report back to the server for a specific stream.
        """

        if stream_number not in range(self.num_streams):
            raise ValueError(f"Invalid stream number {stream_number}")

        rtcp_channel = self.rtcp_idx[stream_number]
        self.logger.debug(f'rtcp report {rtcp_channel}')
        self.connection.send_binary(rtcp_channel, bytes(rtcp))

