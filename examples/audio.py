"""Audio example using the RTSPReader"""

import asyncio
import contextlib
import logging
import sys

from aiortsp.rtsp.reader import RTSPReader

logging.getLogger().setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logging.getLogger().addHandler(handler)


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--logging", type=int, default=20, help="Log level")
    parser.add_argument(
        "--media", type=str, default="audio", help="Media type to request"
    )
    parser.add_argument("url", help="RTSP url")
    args = parser.parse_args()

    # Open a reader (which means RTSP connection, then media session)
    async with RTSPReader(
        args.url, log_level=args.logging, run_loop=True, media_type=args.media
    ) as reader:
        # Iterate on RTP packets
        async for pkt in reader.iter_packets():
            logging.info(
                "AUDIO PKT %s",
                (pkt.cc, pkt.m, pkt.pt, pkt.seq, pkt.ts, pkt.ssrc, len(pkt.data)),
            )
    logging.info("... all done...")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
