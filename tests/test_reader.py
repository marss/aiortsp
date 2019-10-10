import asyncio
import logging
import sys

import pytest
from dpkt.rtp import RTP

from aiortsp.rtsp.reader import RTSPReader
from tests.test_session import handle_client_auth


@pytest.mark.asyncio
async def test_reader():
    count = 0
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPReader('rtspt://127.0.0.1:5554/media.sdp', timeout=2) as reader:
            async for pkt in reader.iter_packets():
                assert isinstance(pkt, RTP)
                count += 1

                if count >= 2:
                    server.close()

        assert count == 2
    finally:
        server.close()


@pytest.mark.asyncio
async def test_reader_reconnect():
    logging.basicConfig()
    count = 0

    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPReader('rtspt://127.0.0.1:5554/media.sdp', run_loop=True, timeout=2, log_level=10) as reader:
            async for pkt in reader.iter_packets():
                print('PKT', len(pkt))
                assert isinstance(pkt, RTP)
                count += 1

                if count == 2:
                    # closing connection to test reconnect
                    reader.connection.close()

                if count == 4:
                    break
    finally:
        server.close()
