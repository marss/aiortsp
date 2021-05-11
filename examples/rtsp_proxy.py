import argparse
import logging

import asyncio
import contextlib

from aiortsp.rtsp.reader import RTSPReader
from aiortsp.rtsp.sdp import SDP
from aiortsp.rtsp.server import RTSPServer, RTPStream


class H264Stream(RTPStream):

    def __init__(self, sdp: SDP):
        self.sdp = sdp

    def to_sdp(self, url) -> str:
        pt = self.sdp.media_payload_type()
        media = self.sdp.get_media(media_type='video')
        fmtp_data = ';'.join(
            '{}={}'.format(k, v)
            for k, v in media.get('attributes', {}).get('fmtp', {}).items()
            if k != 'pt'
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


async def main():
    """
    Run an RTSP Server
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='url to forward')
    args = parser.parse_args()

    async with RTSPServer(port=5554) as server:
        async with RTSPReader(args.url) as reader:
            await asyncio.wait_for(reader.ready.wait(), 10)
            stream = H264Stream(reader.session.sdp)
            async with server.register_stream('/toto.amp', stream):
                # Iterate on RTP packets
                async for pkt in reader.iter_packets():
                    # print('PKT', pkt.seq, pkt.pt, len(pkt))
                    stream.inject(pkt)


if __name__ == '__main__':
    logging.basicConfig(level=10)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
