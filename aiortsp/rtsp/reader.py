"""
Simplified RTP Media reader
"""
import asyncio
import logging
from time import time
from typing import AsyncIterable, Optional, Tuple
from urllib.parse import urlparse

from dpkt.rtp import RTP
from aiortsp.rtcp.parser import RTCP

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.session import RTSPMediaSession, sanitize_rtsp_url
from aiortsp.transport import transport_for_scheme, RTPTransport, RTPTransportClient


class RTSPReader(RTPTransportClient):
    """
    Quick wrapper around base functions to start getting frames from an RTSP feed.

    Usage:

    .. code-block::

        async with RTSPReader('rtsp://foo/bar') as reader:
            async for pkt in reader.iter_packets():
                print(pkt)
    """

    def __init__(
            self, media_url: str, media_types=['video'], timeout=10, log_level=20,
            run_loop=False, **_
    ):
        self.media_url = media_url
        self.media_types = media_types
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.timeout = timeout
        self.run_loop = run_loop
        self.queue: 'asyncio.Queue[RTP]' = asyncio.Queue()
        self._runner = None
        self.connection: Optional[RTSPConnection] = None
        self.transport: Optional[RTPTransport] = None
        self.session: Optional[RTSPMediaSession] = None
        self.payload_types = []
        self.rtp_count = [0] * len(media_types)
        self.rtcp_count = [0] * len(media_types)


    def handle_rtp(self, rtp: RTP, channel_number=0):
        """Queue packets for the iterator"""
        self.rtp_count[channel_number] += 1
        self.logger.debug(f'channel:{channel_number} rtp self.payload_types:{self.payload_types} incoming_type:{rtp.pt}')

        for pt, media_type in self.payload_types:
            if pt == rtp.pt:
                self.logger.debug(f'adding {media_type} {rtp.pt} to queue')
                self.queue.put_nowait((media_type, rtp))
                break

    def handle_rtcp(self, rtcp: RTCP, channel_number=0):
        self.rtcp_count[channel_number] += 1
        self.logger.debug(f'RTCP: {self.rtcp_count} {rtcp}')

    def on_ready(self, connection: RTSPConnection, transport: RTPTransport, session: RTSPMediaSession):
        """Handler on ready to play stream, for sub classes to do their initialisation"""
        if session.sdp:
            for media_type in self.media_types:
                self.logger.debug(f'setting session media to {media_type}')
                pt = session.sdp.media_payload_type(media_type)
                self.payload_types.extend([(pt, media_type)])
        transport.subscribe(self)
        self.connection = connection
        self.transport = transport
        self.session = session

    def handle_closed(self, error):
        """Handler for connection closed, for sub classes to cleanup their state"""
        self.logger.info('connection closed, error: %s', error)
        self.connection = None
        self.transport = None
        self.session = None

    async def run_stream_loop(self):
        """Run stream as a loop, forever restarting unless if cancelled"""
        while True:
            try:
                await self.run_stream()
            except asyncio.CancelledError:
                self.logger.error('Stopping run loop for %s', sanitize_rtsp_url(self.media_url))
                break
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error('Error on stream: %r. Reconnecting...', ex)
                await asyncio.sleep(1)

    async def run_stream(self):
        """
        Setup and play stream, and ensure it stays on.
        """
        self.logger.info('try loading stream %s', sanitize_rtsp_url(self.media_url))

        p_url = urlparse(self.media_url)
        async with RTSPConnection(
                p_url.hostname, p_url.port or 554,
                p_url.username, p_url.password,
                logger=self.logger, timeout=self.timeout
        ) as conn:
            self.logger.info('connected!')

            transport_class = transport_for_scheme(p_url.scheme)
            async with transport_class(conn, logger=self.logger, timeout=self.timeout, num_streams=len(self.media_types)) as transport:
                async with RTSPMediaSession(conn, self.media_url, media_types=self.media_types, transport=transport, logger=self.logger) as sess:

                    self.on_ready(conn, transport, sess)

                    self.logger.info('playing stream...')
                    await sess.play()

                    try:
                        last_keep_alive = time()
                        while conn.running and transport.running:
                            # Check keep alive
                            now = time()
                            if (now - last_keep_alive) > sess.session_keepalive:
                                await sess.keep_alive()
                                last_keep_alive = now

                            await asyncio.sleep(1)

                    except asyncio.CancelledError:
                        self.logger.info('stopping stream...')
                        raise

    async def close(self):
        """ Gracefully close the RTSP session and the connection. """
        if self.session:
            await self.session.teardown()
        if self.connection:
            self.connection.close()
        if self._runner:
            self._runner.cancel()

    async def __aenter__(self):
        self._runner = asyncio.ensure_future(
            self.run_stream_loop() if self.run_loop else self.run_stream())
        self._runner.add_done_callback(lambda *_: self.queue.put_nowait(None))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def iter_packets(self) -> AsyncIterable[Tuple[str, RTP]]:
        """
        Yield RTP packets as they come.
        User can then do whatever they want, without too much boiler plate.
        """
        while True:
            item = await self.queue.get()

            if not item:
                break

            yield item
