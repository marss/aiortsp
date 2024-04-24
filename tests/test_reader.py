import asyncio
import logging
import sys

import pytest
from dpkt.rtp import RTP

from aiortsp.rtsp.reader import RTSPReader
from tests.test_session import handle_client_auth


@pytest.mark.asyncio
async def test_video_reader():
    count = 0
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPReader('rtspt://127.0.0.1:5554/media.sdp', timeout=2, media_types=['video']) as reader:
            async for media_type, pkt in reader.iter_packets():
                assert isinstance(pkt, RTP)
                assert media_type == 'video'
                count += 1

                if count >= 2:
                    server.close()

        assert count == 2
    finally:
        server.close()

@pytest.mark.asyncio
async def test_audio_reader():
    count = 0
    server = await asyncio.start_server(handle_client_auth, '127.0.0.1', 5554)
    try:
        async with RTSPReader('rtspt://127.0.0.1:5554/media.sdp', timeout=2, media_types=['audio']) as reader:
            async for media_type, pkt in reader.iter_packets():
                assert isinstance(pkt, RTP)
                assert media_type == 'audio'
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
        async with RTSPReader('rtspt://127.0.0.1:5554/media.sdp', run_loop=True, timeout=2, media_types=['video'], log_level=10) as reader:
            async for media_type, pkt in reader.iter_packets():
                print('PKT', len(pkt))
                assert isinstance(pkt, RTP)
                assert media_type == 'video'
                count += 1

                if count == 2:
                    # closing connection to test reconnect
                    reader.connection.close()

                if count == 4:
                    break
    finally:
        server.close()
