import argparse
import asyncio
import contextlib
import logging

from aiortsp.rtsp.reader import RTSPReader
from aiortsp.rtsp.sdp import SDP
from aiortsp.rtsp.server import RTPStreamer, RTSPServer


class H264Stream(RTPStreamer):
    def __init__(self, sdp: SDP):
        self.sdp = sdp

    def to_sdp(self, url) -> str:
        pt = 96  # self.sdp.media_payload_type()
        #        media = self.sdp.get_media(media_type='video')
        #        fmtp_data = ';'.join(
        #            '{}={}'.format(k, v)
        #            for k, v in media.get('attributes', {}).get('fmtp', {}).items()
        #            if k != 'pt'
        #        )
        fmtp_data = " "
        clock_rate = 90000  # self.sdp.media_clock_rate()
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


async def main():
    """
    Run an RTSP Server
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="url to forward")
    args = parser.parse_args()

    async with RTSPServer(
        port=5554, users={"Mufasa": "H4kun4m4t4t4"}, accept_auth=["digest"]
    ) as server:
        # async with RTSPReader(args.url) as reader:
        #        await asyncio.wait_for(reader.ready.wait(), 10)
        stream = H264Stream(None)
        server.register_streamer("/toto.amp", stream)
        await asyncio.sleep(100)
        #        # Iterate on RTP packets
        #        async for pkt in reader.iter_packets():
        #            # print('PKT', pkt.seq, pkt.pt, len(pkt))
        #            stream.inject(pkt)


if __name__ == "__main__":
    logging.basicConfig(level=10)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
