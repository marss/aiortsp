"""
RTSPS example using the RTSPReader
"""

import asyncio
import contextlib
import logging
import ssl
import sys

from aiortsp.rtsp.reader import RTSPReader

logging.getLogger().setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logging.getLogger().addHandler(handler)


async def main():
    import argparse
    from urllib.parse import urlparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--logging", type=int, default=20, help="RTSP url")
    parser.add_argument("url", help="RTSPS url")
    args = parser.parse_args()

    p_url = urlparse(args.url)

    if p_url.scheme != "rtsps":
        logging.error("this example only supports rtsp:// URLs")
        sys.exit(1)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    # Open a reader (which means RTSP connection, then media session)
    async with RTSPReader(args.url, log_level=args.logging, run_loop=True, ssl=ssl_ctx) as reader:
        # Iterate on RTP packets
        async for pkt in reader.iter_packets():
            logging.info("PKT %s", (pkt.cc, pkt.m, pkt.pt, pkt.seq, pkt.ts, pkt.ssrc, len(pkt.data)))
    logging.info("... all done...")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
