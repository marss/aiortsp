import asyncio
import functools
import sys

import pytest

from aiortsp.rtsp.auth import DigestAuth
from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.errors import RTSPResponseError
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


@pytest.mark.asyncio
async def test_client_connection():
    queue = asyncio.Queue()

    server = await asyncio.start_server(functools.partial(handle_client, queue), '127.0.0.1', 5554)
    try:
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
    finally:
        server.close()


async def handle_client_auth(client_reader, client_writer):
    parser = RTSPParser()

    while True:
        data = await client_reader.read(10000)
        for msg in parser.parse(data):
            authorized = False
            if 'authorization' in msg.headers:
                # Check it!
                params = DigestAuth._parse_digest_header(msg.headers['authorization'].split(' ', 1)[-1])
                print("PARAMS", params)
                if params.get('nonce') == '0024e47aY398109708de9ccd8056c58a068a59540a99d3' and \
                    params.get('realm') == 'AXIS_ACCC8E000AA9' and \
                    params.get('opaque') == '123soleil' and \
                    params.get('uri') == 'rtsp://cam/axis-media/media.amp' and \
                    params.get('username') == 'root' and \
                    params.get('response') == '7daaf0f4e40fdff42cff28260f37914d':
                    authorized = True

            if authorized:
                client_writer.write("""RTSP/1.0 200 OK\r\nCSeq: {}\r\n\r\n""".format(msg.headers.get('cseq', 0)).encode())
            else:
                client_writer.write("""RTSP/1.0 401 Unauthorized\r
CSeq: {}\r
WWW-Authenticate: Digest realm="AXIS_ACCC8E000AA9", nonce="0024e47aY398109708de9ccd8056c58a068a59540a99d3", opaque="123soleil"\r
\r
""".format(msg.headers.get('cseq', 0)).encode())


@pytest.mark.asyncio
async def test_client_auth_no_credentials():
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPConnection('127.0.0.1', 5554) as conn:
            with pytest.raises(RTSPResponseError):
                await conn.send_request('DESCRIBE', 'rtsp://cam/axis-media/media.amp', timeout=2)
    finally:
        server.close()


@pytest.mark.asyncio
async def test_client_auth_invalid_credentials():
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPConnection('127.0.0.1', 5554, username='toto', password='hello') as conn:
            with pytest.raises(RTSPResponseError):
                await conn.send_request('DESCRIBE', 'rtsp://cam/axis-media/media.amp', timeout=2)
    finally:
        server.close()


@pytest.mark.asyncio
async def test_client_auth():
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPConnection('127.0.0.1', 5554, username='root', password='admin123') as conn:
            resp = await conn.send_request('DESCRIBE', 'rtsp://cam/axis-media/media.amp', timeout=2)
            assert resp
            assert resp.status == 200
    finally:
        server.close()
