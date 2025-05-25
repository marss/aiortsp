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
    parser.add_argument('--media-types', type=str, default=None, help='Comma-separated list of media types to request (e.g., "video,audio").')
    parser.add_argument('--all-streams', action='store_true', help='Request all available media streams from SDP.')
    parser.add_argument('url', help='RTSP url')
    args = parser.parse_args()

    logger.setLevel(args.logging)

    media_types_to_request = None
    use_all_streams_flag = False
    if args.all_streams:
        use_all_streams_flag = True
    elif args.media_types:
        media_types_to_request = [mt.strip() for mt in args.media_types.split(',')]
    else:
        use_all_streams_flag = True

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

            async with RTSPMediaSession(
                conn,
                media_url,
                transport,  # This is the template_transport
                logger=logger,
                media_types=media_types_to_request,
                use_all_available_streams=use_all_streams_flag
            ) as sess:

                if sess.transports:  # Check if any transports were successfully set up
                    for media_type, actual_transport in sess.transports.items():
                        logger.info(f"Subscribing RTP/RTCP probe to transport for media type: {media_type}")
                        actual_transport.subscribe(probe)
                else:
                    logger.warning("No media streams were successfully set up by RTSPMediaSession.")

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
