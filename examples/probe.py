import asyncio
import contextlib

import logging

from aiortsp.transport import RTPTransportClient, transport_for_scheme
from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.session import RTSPMediaSession

logger = logging.getLogger('rtsp_client')
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')


class Probe(RTPTransportClient):

    def __init__(self):
        self.rtp_count = 0
        self.rtcp_count = 0

    def handle_rtp(self, rtp):
        self.rtp_count += 1

    def handle_rtcp(self, rtcp):
        self.rtcp_count += 1
        logger.debug('RTCP received: %s', rtcp)


async def main():
    import argparse
    from urllib.parse import urlparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--logging', type=int, default=20, help='RTSP url')
    parser.add_argument('-a', '--address', default='127.0.0.1', help='destination UDP address')
    parser.add_argument('-A', '--auth', type=str, help='Auth to force ')
    parser.add_argument('-p', '--props', default=None, help='Stream props (guessed if not provided)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='UDP timeout')
    parser.add_argument('url', help='RTSP url')
    args = parser.parse_args()

    logger.setLevel(args.logging)

    p_url = urlparse(args.url)
    media_url = args.url
    probe = Probe()

    async with RTSPConnection(
            p_url.hostname,
            p_url.port or 554,
            p_url.username,
            p_url.password,
            logger=logger
    ) as conn:

        logger.info('connected!')

        # Detects if UDP or TCP must be used for RTP transport
        transport_class = transport_for_scheme(p_url.scheme)

        async with transport_class(conn, logger=logger, timeout=args.timeout) as transport:

            # This is where wa actually subscribe to data
            transport.subscribe(probe)

            async with RTSPMediaSession(conn, media_url, transport, logger=logger) as sess:

                await sess.play()

                try:
                    while conn.running and transport.running:
                        await asyncio.sleep(sess.session_keepalive)
                        await sess.keep_alive()

                        logger.info('received %s RTP, %s RTCP', probe.rtp_count, probe.rtcp_count)

                except asyncio.CancelledError:
                    logger.info('stopping stream...')


if __name__ == '__main__':
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
