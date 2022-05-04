import argparse
import asyncio
import contextlib
import logging
from urllib.parse import urlparse

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.server.base import RTSPServer
from aiortsp.rtsp.server.streamer import RTPStreamer, StreamNotFound
from aiortsp.rtsp.session import RTSPMediaSession
from aiortsp.transport import RTPTransportClient, transport_for_scheme

logger = logging.getLogger("rtsp_client")


class ProxyStreamer(RTPTransportClient, RTPStreamer):
    def __init__(self, url: str, path: str = "/video"):
        RTPStreamer.__init__(self)
        self.url = url
        self.sdp = None
        self.task = None
        self.playing = False

    def describe(self, url):
        if self.sdp is None:
            raise StreamNotFound("sdp not ready yet")

        return "application/sdp", self.build_sdp(url)

    def handle_rtp(self, rtp):
        if self.playing:
            self.send_rtp("proxied", rtp)

    def handle_rtcp(self, rtcp):
        """TODO: do something with this?"""

    def build_sdp(self, requested_url: str) -> str:
        assert self.sdp

        url = urlparse(requested_url)

        pt = self.sdp.media_payload_type()
        media = self.sdp.get_media(media_type="video")
        fmtp_data = ";".join(
            "{}={}".format(k, v)
            for k, v in media.get("attributes", {}).get("fmtp", {}).items()
            if k != "pt"
        )
        clock_rate = self.sdp.media_clock_rate()
        return f"""v=0
o=- 0 1 IN IP4 {url.hostname}
s=Session streamed with aiortsp
i=rtsp-server
t=0 0
a=tool:aiortsp
a=type:broadcast
a=range:npt=now-
a=control:{url.geturl()}
m=video 0 RTP/AVP {pt}
c=IN IP4 0.0.0.0
a=rtpmap:{pt} H264/{clock_rate}
a=fmtp:{pt} {fmtp_data}
"""

    def setup_stream(self, session_id, setup_url):
        logger.info("setting up stream %s for session %s", setup_url, session_id)
        return "proxied"

    def play(self, session_id, **_):
        self.playing = True

    def pause(self, session_id):
        self.playing = False

    def teardown(self, session_id):
        self.playing = False

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        self.task = asyncio.ensure_future(self.handle_stream())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await self.task

    async def handle_stream(self):

        p_url = urlparse(self.url)
        media_url = self.url

        async with RTSPConnection(
            p_url.hostname,
            p_url.port or 554,
            p_url.username,
            p_url.password,
            logger=logger,
        ) as conn:

            logger.info("connected!")

            # Detects if UDP or TCP must be used for RTP transport
            transport_class = transport_for_scheme(p_url.scheme)

            async with transport_class(conn, logger=logger, timeout=10) as transport:

                # This is where wa actually subscribe to data
                transport.subscribe(self)

                async with RTSPMediaSession(
                    conn, media_url, transport, logger=logger
                ) as sess:

                    self.sdp = sess.sdp

                    await sess.play()

                    try:
                        while conn.running and transport.running:
                            await asyncio.sleep(sess.session_keepalive)
                            await sess.keep_alive()

                            logger.info("keep alive")

                    except asyncio.CancelledError:
                        logger.info("stopping stream...")


USERS = {"Mufasa": "H4kun4m4t4t4", "admin": "admin"}


async def main():
    """
    Run an RTSP Server
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--port", type=int, default=8554, help="RTSP port (default: 8554)"
    )
    parser.add_argument(
        "-l", "--logging", type=int, default=20, help="Log level (default: 20)"
    )
    parser.add_argument(
        "-P", "--path", default="/video", help="Media path (default: /video)"
    )
    parser.add_argument("url", help="url to forward")
    args = parser.parse_args()

    logging.basicConfig(level=args.logging)

    async with ProxyStreamer(url=args.url, path=args.path) as streamer:
        server = RTSPServer(streamer, port=args.port, users=USERS)
        await server.run()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
