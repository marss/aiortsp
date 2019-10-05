import asyncio
import functools
import sys

import pytest

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.parser import RTSPParser


async def handle_client(queue, client_reader, client_writer):

    count = 0
    parser = RTSPParser()

    while True:
        data = await client_reader.read(10000)

        for msg in parser.parse(data):
            if count == 0:
                assert msg.content == 'Dumb ass!'
                assert msg.headers['content-length'] == str(len(b'Dumb ass!'))

            resp = f"""RTSP/1.0 200 OK\r
CSeq: {msg.cseq}\r
\r
"""
            if count == 0:
                resp += f"""ANNOUNCE rtsp://foo/bar.avi RTSP/1.0\r
CSeq: {msg.cseq + 1}\r
\r
"""
            client_writer.write(resp.encode())
            count += 1
            queue.put_nowait(msg)


@pytest.mark.skipif(sys.version_info < (3, 7), reason='asyncio.start_server not supported')
@pytest.mark.asyncio
async def test_client_connection():
    queue = asyncio.Queue()

    async with await asyncio.start_server(functools.partial(handle_client, queue), '127.0.0.1', 5554):

        async with RTSPConnection('127.0.0.1', 5554, 'foo', 'bar') as conn:

            # Send an OPTIONS request
            resp = await conn.send_request('OPTIONS', '*', timeout=2, body=b'Dumb ass!')
            assert resp
            assert resp.status == 200

            # Ensure the other side have seen a request
            req = await asyncio.wait_for(queue.get(), 2)
            assert req.type == 'request'
            assert req.method == 'OPTIONS'
            assert req.cseq == resp.cseq

            # Then it should have sent an announce, and got a 551 reply
            req = await asyncio.wait_for(queue.get(), 2)
            assert req.type == 'response'
            assert req.status == 551
            assert req.cseq == resp.cseq + 1
