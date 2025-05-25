import asyncio

import pytest

from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.rtsp.parser import RTSPParser, RTSPRequest
from aiortsp.rtsp.session import RTSPMediaSession
from aiortsp.transport import TCPTransport


async def handle_client_auth(client_reader, client_writer):
    parser = RTSPParser()
    playing = False
    # Store which streams have been set up and their interleaved channels
    # Example: {'video': (0, 1), 'audio': (2, 3)}
    server_active_streams = {} 
    next_channel = 0 # For assigning interleaved channels

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
                sdp_body = (
                    "v=0\r\n"
                    "o=- 12345 1 IN IP4 127.0.0.1\r\n"
                    "s=Test Multi-Stream\r\n"
                    "t=0 0\r\n"
                    "a=control:rtsp://localhost:5554/\r\n" # Base control URL for the session
                    "m=video 0 RTP/AVP 96\r\n"
                    "c=IN IP4 0.0.0.0\r\n"
                    "a=rtpmap:96 H264/90000\r\n"
                    "a=fmtp:96 packetization-mode=1\r\n"
                    "a=control:streamid=0\r\n" # Relative control URL for video
                    "m=audio 0 RTP/AVP 97\r\n"
                    "c=IN IP4 0.0.0.0\r\n"
                    "a=rtpmap:97 MPA/90000/2\r\n"
                    "a=control:streamid=1\r\n" # Relative control URL for audio
                )
                response += 'Content-Type: application/sdp\r\n'
                response += 'Content-Base: rtsp://localhost:5554/\r\n' # Matches a=control in SDP
                response += 'Server: Dummy Test Server\r\n'
                response += f'Content-Length: {len(sdp_body)}\r\n'
                response += '\r\n'
                response += sdp_body
            elif msg.method == 'SETUP':
                # Determine stream type from URL (e.g., /streamid=0)
                stream_id_part = msg.url.split('/')[-1] # Gets 'streamid=X' or the full path if no slash
                
                # More robust parsing of control attribute
                if "streamid=0" in msg.url:
                    stream_type = 'video'
                    rtp_channel = next_channel
                    rtcp_channel = next_channel + 1
                    next_channel += 2
                    server_active_streams[stream_type] = (rtp_channel, rtcp_channel)
                    response += f'Transport: RTP/AVP/TCP;unicast;interleaved={rtp_channel}-{rtcp_channel};ssrc=VIDEOSSRC;mode="PLAY"\r\n'
                elif "streamid=1" in msg.url:
                    stream_type = 'audio'
                    rtp_channel = next_channel
                    rtcp_channel = next_channel + 1
                    next_channel += 2
                    server_active_streams[stream_type] = (rtp_channel, rtcp_channel)
                    response += f'Transport: RTP/AVP/TCP;unicast;interleaved={rtp_channel}-{rtcp_channel};ssrc=AUDIOSSRC;mode="PLAY"\r\n'
                else:
                    # Fallback or error if control URL is not recognized
                    response = 'RTSP/1.0 404 Not Found\r\nCSeq: {}\r\n\r\n'.format(msg.cseq)
                    client_writer.write(response.encode())
                    continue

                response += 'Session: testsessionid;timeout=60\r\n'
            elif msg.method == 'PLAY':
                playing = True
                # Session ID must be in PLAY request if session is established
                if 'Session' not in msg.headers or msg.headers['Session'] != 'testsessionid':
                    response = 'RTSP/1.0 454 Session Not Found\r\nCSeq: {}\r\n\r\n'.format(msg.cseq)
                    client_writer.write(response.encode())
                    continue

            response += '\r\n'
            print('RESPONSE', response)
            client_writer.write(response.encode())

            if playing:
                # Send dummy RTP and RTCP for each active stream
                for stream_type, (rtp_ch, rtcp_ch) in server_active_streams.items():
                    # Dummy RTP packet (very basic)
                    # $ + channel_id (1 byte) + length (2 bytes) + RTP payload
                    rtp_payload = b'\x80\x60\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' # Minimal H264/MPA
                    rtp_header = bytearray([ord('$'), rtp_ch, 0, len(rtp_payload)])
                    rtp_packet = rtp_header + rtp_payload
                    
                    print(f"Sending RTP for {stream_type} on channel {rtp_ch}")
                    client_writer.write(rtp_packet)
                    client_writer.write(rtp_packet) # Send two packets

                    # Dummy RTCP Sender Report (very basic)
                    # $ + channel_id (1 byte) + length (2 bytes) + RTCP SR payload
                    # For simplicity, using a generic SR. Real SR would have SSRC matching SETUP response.
                    ssrc = b'\xDE\xAD\xBE\xEF' # Dummy SSRC
                    if stream_type == 'video': ssrc = b'\xVI\xDE\xOS\xRC'
                    if stream_type == 'audio': ssrc = b'\xAU\xDI\xOS\xRC'

                    rtcp_sr_payload = b'\x80\xc8\x00\x06' + ssrc + b'\x00\x00\x00\x00'*6 # Minimal SR
                    rtcp_header = bytearray([ord('$'), rtcp_ch, 0, len(rtcp_sr_payload)])
                    rtcp_packet = rtcp_header + rtcp_sr_payload
                    
                    print(f"Sending RTCP for {stream_type} on channel {rtcp_ch}")
                    client_writer.write(rtcp_packet)
                playing = False # Reset after sending packets for this PLAY

@pytest.fixture
async def mock_rtsp_server(event_loop):
    server = await event_loop.create_server(
        lambda: asyncio.Protocol(), # Placeholder, actual handler is passed to start_server
        '127.0.0.1', 5554
    )
    # The server object from create_server doesn't have a direct way to set the protocol factory
    # for each connection after creation. We'll start and close the server within each test.
    # This fixture is more for managing the event loop and ensuring cleanup.
    yield '127.0.0.1', 5554 # Host, Port
    # Server closing will be handled in each test function's finally block
    # For a real fixture managing the server, we'd need a custom server class or more complex setup.


async def run_test_scenario(host, port, media_types=None, use_all_streams=False, expected_transports=0, expected_media_in_stats=None):
    server = await asyncio.start_server(handle_client_auth, host, port)
    if expected_media_in_stats is None:
        expected_media_in_stats = []

    try:
        async with RTSPConnection(host, port, timeout=5) as conn: # Increased timeout
            async with TCPTransport(conn) as transport:
                async with RTSPMediaSession(
                    conn, 
                    f'rtsp://{host}:{port}/', # Base URL for the session
                    transport, 
                    media_types=media_types, 
                    use_all_available_streams=use_all_streams
                ) as sess:
                    
                    if expected_transports > 0:
                        await sess.play()
                        await asyncio.sleep(0.5) # Allow time for packets to be "received"
                    
                    assert len(sess.transports) == expected_transports
                    for media_type in expected_media_in_stats:
                        assert media_type in sess.transports
                        assert media_type in sess.stats
                        assert sess.stats[media_type].received > 0, f"No RTP packets received for {media_type}"
                        # Check for RTCP stats as well if applicable
                        rtcp_report = sess.stats[media_type].build_rtcp()
                        assert rtcp_report is not None, f"RTCP report not generated for {media_type}"

    finally:
        server.close()
        await server.wait_closed()

@pytest.mark.asyncio
async def test_session_video_only(mock_rtsp_server):
    host, port = mock_rtsp_server
    await run_test_scenario(host, port, media_types=['video'], expected_transports=1, expected_media_in_stats=['video'])

@pytest.mark.asyncio
async def test_session_audio_only(mock_rtsp_server):
    host, port = mock_rtsp_server
    await run_test_scenario(host, port, media_types=['audio'], expected_transports=1, expected_media_in_stats=['audio'])

@pytest.mark.asyncio
async def test_session_video_and_audio(mock_rtsp_server):
    host, port = mock_rtsp_server
    await run_test_scenario(host, port, media_types=['video', 'audio'], expected_transports=2, expected_media_in_stats=['video', 'audio'])

@pytest.mark.asyncio
async def test_session_all_streams(mock_rtsp_server):
    host, port = mock_rtsp_server
    await run_test_scenario(host, port, use_all_streams=True, expected_transports=2, expected_media_in_stats=['video', 'audio'])

@pytest.mark.asyncio
async def test_session_non_existent_stream(mock_rtsp_server):
    host, port = mock_rtsp_server
    await run_test_scenario(host, port, media_types=['application'], expected_transports=0)

@pytest.mark.asyncio
async def test_original_single_stream_compatibility(mock_rtsp_server):
    # This test ensures that when media_types is not specified (or is a single string),
    # and use_all_available_streams is False, it defaults to the first media type (video).
    # The RTSPMediaSession constructor was modified to take media_types (plural)
    # or a single media_type string for backward compatibility.
    # The default behavior if only one string is passed is to treat it as ['video'] (the old default).
    # However, current RTSPMediaSession defaults to media_type='video' if media_types is None and use_all_available_streams=False
    host, port = mock_rtsp_server
    
    server = await asyncio.start_server(handle_client_auth, host, port)
    try:
        async with RTSPConnection(host, port, timeout=5) as conn:
            async with TCPTransport(conn) as transport:
                # Test default behavior (should pick 'video' based on current RTSPMediaSession constructor default)
                async with RTSPMediaSession(conn, f'rtsp://{host}:{port}/', transport) as sess:
                    assert len(sess.media_types) == 1 
                    # Default is 'video' if nothing else specified
                    assert sess.media_types[0] == 'video' 
                    
                    await sess.play()
                    await asyncio.sleep(0.5)
                    
                    assert len(sess.transports) == 1
                    assert 'video' in sess.transports
                    assert sess.stats['video'].received > 0
                    rtcp = sess.stats['video'].build_rtcp()
                    assert rtcp

                # Test explicit single string 'audio'
                async with RTSPMediaSession(conn, f'rtsp://{host}:{port}/', transport, media_type='audio') as sess_audio:
                    assert sess_audio.media_types == ['audio']
                    
                    await sess_audio.play()
                    await asyncio.sleep(0.5)

                    assert len(sess_audio.transports) == 1
                    assert 'audio' in sess_audio.transports
                    assert sess_audio.stats['audio'].received > 0
                    rtcp_audio = sess_audio.stats['audio'].build_rtcp()
                    assert rtcp_audio

    finally:
        server.close()
        await server.wait_closed()
