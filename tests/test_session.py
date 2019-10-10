import asyncio

import pytest

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.parser import RTSPParser, RTSPRequest
from aiortsp.rtsp.session import RTSPMediaSession
from aiortsp.transport import TCPTransport


async def handle_client_auth(client_reader, client_writer):
    parser = RTSPParser()
    playing = False

    while True:
        data = await client_reader.read(10000)

        if not data:
            break

        for msg in parser.parse(data):
            assert isinstance(msg, RTSPRequest)
            print('MSG', msg)
            response = 'RTSP/1.0 200 OK\r\nCSeq: {}\r\n'.format(msg.cseq)
            if msg.method == 'OPTIONS':
                response += 'Public: DESCRIBE, SETUP, TEARDOWN, PLAY, PAUSE\r\n'
            elif msg.method == 'DESCRIBE':
                response += 'Content-Type: application/sdp\r\n'
                response += 'Content-Base: rtsp://cam/media.sdp/\r\n'
                response += 'Server: Dummy Test server\r\n'
                response += 'Content-Length: 617\r\n'
                response += '\r\n'
                response += 'v=0\r\n'
                response += 'o=- 17428449743163035608 1 IN IP4 10.10.0.77\r\n'
                response += 's=Session streamed with GStreamer\r\n'
                response += 'i=rtsp-server\r\n'
                response += 't=0 0\r\n'
                response += 'a=tool:GStreamer\r\n'
                response += 'a=type:broadcast\r\n'
                response += 'a=range:npt=now-\r\n'
                response += 'a=control:rtsp://10.10.0.77/axis-media/media.amp\r\n'
                response += 'm=video 0 RTP/AVP 96\r\n'
                response += 'c=IN IP4 0.0.0.0\r\n'
                response += 'b=AS:50000\r\n'
                response += 'a=rtpmap:96 H264/90000\r\n'
                response += 'a=fmtp:96 packetization-mode=1;profile-level-id=4d0029;sprop-parameter-sets=Z00AKeKQCgC3YC3AQEBpB4kRUA==,aO48gA==\r\n'
                response += 'a=ts-refclk:local\r\n'
                response += 'a=mediaclk:sender\r\n'
                response += 'a=control:rtsp://10.10.0.77/axis-media/media.amp/stream=0\r\n'
                response += 'a=framerate:25.000000\r\n'
                response += 'a=transform:1.000000,0.000000,0.000000;0.000000,1.000000,0.000000;0.000000,0.000000,1.000000\r\n'
            elif msg.method == 'SETUP':
                response += 'Transport: RTP/AVP/TCP;unicast;interleaved=0-1;ssrc=E6EC9FEF;mode="PLAY"\r\n'
                response += 'Session: 2sY7Pd2EPx8JY50-;timeout=60\r\n'
            elif msg.method == 'PLAY':
                playing = True
            response += '\r\n'
            print('RESPONSE', response)
            client_writer.write(response.encode())

            if playing:
                # Send 2 RTP packets
                rtp = bytearray.fromhex('2400002080605eaac639ab5e13cd9b86674d0029e29019077f1180b7010101a41e244540'
                                        '2400001080605eabc639ab5e13cd9b8668ee3c80')
                client_writer.write(rtp)

                # Send an SR
                sr = bytearray.fromhex('80c8000677ae8d65e051bc2bea33b0001fa8034c0000000000000000')
                msg = bytearray([ord('$'), 1, 0, len(sr)])
                msg.extend(sr)
                client_writer.write(msg)


@pytest.mark.asyncio
async def test_session():
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPConnection('127.0.0.1', 5554, timeout=2) as conn:
            async with TCPTransport(conn) as transport:
                async with RTSPMediaSession(conn, 'rtsp://cam/media.sdp', transport) as sess:
                    rtcp = sess.stats.build_rtcp()
                    assert rtcp is None
                    await sess.play()
                    await asyncio.sleep(0.2)
                    rtcp = sess.stats.build_rtcp()
                    assert rtcp
                    assert sess.stats.received == 2
    finally:
        server.close()
