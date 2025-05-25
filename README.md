```markdown
# aiortsp - Asynchronous RTSP Client for Python

`aiortsp` is a Python library providing an asynchronous client for the Real Time Streaming Protocol (RTSP). It's built on `asyncio` and allows for robust and efficient communication with RTSP servers to control and receive media streams.

## Features

*   Asynchronous RTSP client operations (OPTIONS, DESCRIBE, SETUP, PLAY, PAUSE, TEARDOWN, GET_PARAMETER).
*   Supports TCP and UDP (via `aiortp`) for RTP transport.
*   Handles Digest and Basic authentication.
*   SDP parsing for media stream information.
*   Extensible RTP transport mechanism.
*   Support for multiple media streams per session.

## Installation

```bash
pip install aiortsp
```

For UDP transport, you might also need `aiortp`:

```bash
pip install aiortp
```

## Basic Usage

Here's a simple example of how to connect to an RTSP server, start streaming, and receive RTP packets:

```python
import asyncio
import logging
from aiortsp.rtsp.connection import RTSPConnection
from aiortsp.transport import transport_for_scheme, RTPTransportClient
from aiortsp.rtsp.session import RTSPMediaSession
from urllib.parse import urlparse

logger = logging.getLogger('aiortsp')
logging.basicConfig(level=logging.DEBUG)

class MyRTPReceiver(RTPTransportClient):
    def handle_rtp(self, rtp_packet):
        logger.info(f"Received RTP packet: {rtp_packet.sequence_number}, len:{len(rtp_packet.data)}")
    
    def handle_rtcp(self, rtcp_packet):
        logger.info(f"Received RTCP packet: {rtcp_packet}")

async def main(url):
    p_url = urlparse(url)
    conn = RTSPConnection(
        host=p_url.hostname,
        port=p_url.port or 554,
        username=p_url.username,
        password=p_url.password
    )

    try:
        await conn.connect()
        logger.info("Connected to RTSP server.")

        # Use TCP transport by default for 'rtsp://'
        transport_class = transport_for_scheme(p_url.scheme if p_url.scheme in ['rtsps', 'rtspu'] else 'rtsp')
        
        async with transport_class(conn) as transport:
            receiver = MyRTPReceiver()
            transport.subscribe(receiver) # Subscribe to receive RTP/RTCP data

            # By default, RTSPMediaSession will try to set up the first video stream found.
            # You can specify media_types=['video', 'audio'] or use_all_available_streams=True
            async with RTSPMediaSession(conn, url, transport) as session:
                await session.play()
                logger.info("PLAY command sent. Streaming started.")
                
                try:
                    while conn.running and transport.running:
                        await asyncio.sleep(session.session_keepalive if session.session_keepalive > 0 else 5)
                        if session.session_id: # Check if session is active
                           logger.debug("Sending keep-alive (OPTIONS or GET_PARAMETER).")
                           await session.keep_alive()
                except asyncio.CancelledError:
                    logger.info("Streaming cancelled.")
                finally:
                    logger.info("Stopping stream.")
                    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if conn.running:
            await conn.close()
        logger.info("Connection closed.")

if __name__ == '__main__':
    rtsp_url = "rtsp://user:pass@your_rtsp_server_ip/path" # Replace with your RTSP URL
    # Example: rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov
    asyncio.run(main(rtsp_url))
```

## Probing RTSP Streams

The `examples/probe.py` script can be used to connect to an RTSP stream, print SDP information, and display RTP/RTCP packet counts.

```bash
python examples/probe.py rtsp://your_rtsp_server_ip/path
```

You can specify media types to request:
```bash
python examples/probe.py --media-types "video,audio" rtsp://your_rtsp_server_ip/path
```
Or request all available streams:
```bash
python examples/probe.py --all-streams rtsp://your_rtsp_server_ip/path
```

## Decoding Video and Audio with PyAV

`aiortsp` can be used in conjunction with libraries like PyAV to decode video and audio streams received from an RTSP server. PyAV provides Python bindings for the FFmpeg libraries.

### Prerequisites

You need to install PyAV and its dependencies. FFmpeg is a core dependency.

```bash
pip install av
```

Please refer to the [PyAV installation documentation](https://pyav.org/docs/stable/overview/installation.html) for detailed instructions on installing FFmpeg for your operating system.

### Example Overview

The `examples/pyav_example.py` script demonstrates how to:
1.  Connect to an RTSP server using `aiortsp`.
2.  Set up one or more media streams (e.g., video and audio).
3.  For each stream, use PyAV's `CodecContext` to decode the incoming RTP packets.
4.  Log basic information about the decoded frames.

This example focuses on showing the integration and is not a full-fledged media player.

### Key Code Snippets

Here are some illustrative snippets showing the core concepts:

**1. Setting up `RTSPMediaSession` for multiple streams:**

```python
# In main_decoder_loop from examples/pyav_example.py (conceptual)
from aiortsp.rtsp.session import RTSPMediaSession
from aiortsp.transport import transport_for_scheme

# ... (RTSPConnection setup) ...

# Use TCP transport by default for 'rtsp://'
transport_class = transport_for_scheme(p_url.scheme if p_url.scheme in ['rtsps', 'rtspu'] else 'rtsp')
template_transport = transport_class(conn, logger=logger.getChild("RTPTransport"))

media_session = RTSPMediaSession(
    conn,
    media_url=url, # Original URL for DESCRIBE and SETUP
    transport_template=template_transport,
    media_types=['video', 'audio'], # Request specific types
    # Or use_all_available_streams=True for all SDP streams
    logger=logger.getChild("RTSPMediaSession")
)
await media_session.setup()
```

**2. Per-stream handler (`StreamDecoder` class structure):**

```python
# Conceptual structure from examples/pyav_example.py
import av # PyAV library
import base64
import binascii

# Mapping SDP encoding names to PyAV codec names
SDP_TO_PYAV_CODEC_MAP = {
    'H264': 'h264',
    'MPEG4-GENERIC': 'aac', # Often for AAC
    'PCMA': 'pcm_alaw',
    'PCMU': 'pcm_mulaw',
}

class StreamDecoder:
    def __init__(self, media_type, rtpmap_info, fmtp_params):
        self.media_type = media_type
        self.rtpmap = rtpmap_info
        self.fmtp_params = fmtp_params
        self.codec_ctx = None
        self.decoded_frames_count = 0

        encoding_name = self.rtpmap.get('encoding', '').upper()
        codec_name = SDP_TO_PYAV_CODEC_MAP.get(encoding_name)

        if codec_name:
            try:
                self.codec_ctx = av.codec.CodecContext.create(codec_name, 'r') # 'r' for read/decode
                self._configure_extradata()
            except av.AVError as e:
                print(f"Error creating codec {codec_name} for {media_type}: {e}")

    def _configure_extradata(self):
        if not self.codec_ctx: return

        # Example: H.264 sprop-parameter-sets (SPS/PPS)
        if self.codec_ctx.name == 'h264' and 'sprop-parameter-sets' in self.fmtp_params:
            sprop = self.fmtp_params['sprop-parameter-sets']
            sps_pps_list = sprop.split(',')
            extradata = bytearray()
            for nal_b64 in sps_pps_list:
                try:
                    nal_bytes = base64.b64decode(nal_b64)
                    extradata.extend(b'\x00\x00\x00\x01' + nal_bytes) # Prepend Annex B start code
                except binascii.Error:
                    continue # Handle error
            if extradata:
                self.codec_ctx.extradata = bytes(extradata)
        
        # Example: AAC config from FMTP
        elif self.codec_ctx.name == 'aac' and 'config' in self.fmtp_params:
            aac_config_hex = self.fmtp_params['config']
            try:
                self.codec_ctx.extradata = binascii.unhexlify(aac_config_hex)
            except binascii.Error:
                pass # Handle error


    def handle_rtp_packet(self, rtp_packet):
        if not self.codec_ctx or self.decoded_frames_count >= 5: # Decode a few frames
            return
        try:
            # codec_ctx.parse() is for codecs that need explicit parsing before decoding
            # For many simple RTP payloads, parsing might not be strictly needed if packets are full frames.
            # However, for H.264, it expects NAL units.
            # WARNING: This does NOT handle H.264 FU-A fragmentation units correctly.
            av_packets = self.codec_ctx.parse(rtp_packet.data)
            for av_packet in av_packets:
                frames = self.codec_ctx.decode(av_packet)
                for frame in frames:
                    self.decoded_frames_count += 1
                    print(f"Decoded {self.media_type} frame {self.decoded_frames_count}: PTS={frame.pts}")
                    if self.decoded_frames_count >= 5: break
        except av.AVError as e:
            # Handle decoding errors, e.g., needs more data
            pass 
```

**3. Subscribing handlers to transports:**

```python
# In main_decoder_loop, after media_session.setup()
# conceptual from examples/pyav_example.py

stream_decoders = {}
if media_session.is_setup:
    for media_type, transport_instance in media_session.transports.items():
        # Get rtpmap and fmtp from session.sdp for this media_type
        media_description = media_session.sdp.get_media(media_type)
        if media_description:
            rtpmap_info = media_description['attributes'].get('rtpmap')
            fmtp_params_str = media_description['attributes'].get('fmtp')
            # Parse fmtp_params_str into a dict if needed
            fmtp_params = {} # Simplified; real parsing is more complex
            if fmtp_params_str:
                parts = fmtp_params_str.split(';')
                for part in parts[1:]: # Skip format number
                    if '=' in part:
                        key, value = part.split('=',1)
                        fmtp_params[key.strip().lower()] = value.strip()

            if rtpmap_info:
                decoder = StreamDecoder(media_type, rtpmap_info, fmtp_params)
                if decoder.codec_ctx:
                    transport_instance.subscribe(
                        rtp_handler=decoder.handle_rtp_packet,
                        # rtcp_handler=decoder.handle_rtcp_packet, (optional)
                        # close_handler=decoder.handle_closed (optional)
                    )
                    stream_decoders[media_type] = decoder
```

### How it Works

1.  **SDP (Session Description Protocol):** When `media_session.setup()` is called, `aiortsp` sends a `DESCRIBE` request to the RTSP server. The server responds with an SDP description. This SDP contains information about the available media streams, including:
    *   Media types (video, audio).
    *   Encoding formats (e.g., H.264, AAC).
    *   RTP mapping (`rtpmap`): Defines the payload type and clock rate.
    *   Format-specific parameters (`fmtp`): Contains crucial details like H.264 `sprop-parameter-sets` (SPS/PPS NAL units) or AAC `config` (AudioSpecificConfig).

2.  **Extradata:** Some codecs, notably H.264 and AAC, require "extradata" to initialize the decoder.
    *   For H.264, this is typically the SPS (Sequence Parameter Set) and PPS (Picture Parameter Set). These are often provided in the `sprop-parameter-sets` field of the `a=fmtp` line in the SDP, Base64 encoded.
    *   For AAC, an `AudioSpecificConfig` (often in hex format in the `config` field of `a=fmtp`) is needed.
    The `StreamDecoder` attempts to parse this from the SDP's `fmtp` attributes and set it on `codec_ctx.extradata`.

3.  **Packet Processing:**
    *   `aiortsp` handles the RTSP signaling and receives RTP packets for each configured stream via its transport instances.
    *   The subscribed `handle_rtp_packet` method in `StreamDecoder` receives the raw RTP payload.
    *   `codec_ctx.parse(rtp_packet.data)`: This PyAV method attempts to parse the RTP payload data. For some codecs, it might group data from multiple RTP packets to form a complete "Access Unit" or frame. For H.264, it expects NAL units.
    *   `codec_ctx.decode(av_packet)`: This method decodes the parsed `AVPacket` (from `parse()`) into one or more `AVFrame` objects.

### Important Considerations & Limitations

*   **H.264 RTP Packetization (FU-A):** A significant challenge with H.264 over RTP is that large NAL units (like I-frames) are often fragmented across multiple RTP packets using Fragmentation Units (FU-A). The basic `codec_ctx.parse()` in PyAV **does not handle reassembly of FU-A fragmented NAL units**. For robust H.264 decoding, you would need to implement or use an RTP de-packetizer for H.264 that reconstructs complete NAL units from FU-A packets before passing them to PyAV. The example script likely simplifies this and may only work with H.264 streams that use single NAL unit packets or if the server sends SPS/PPS in-band frequently.
*   **Codec Support:** The ability to decode a stream depends on the codecs supported by the FFmpeg build used by PyAV. Ensure your FFmpeg installation includes decoders for the stream types you intend to handle (e.g., `libx264`, `libfdk_aac`).
*   **Error Handling:** The example provides basic error handling. Production applications would need more sophisticated mechanisms to manage network issues, decoding errors, and stream interruptions.
*   **Timestamps and Synchronization:** The example focuses on decoding. Proper media playback requires careful handling of Presentation Timestamps (PTS) from decoded frames and synchronization between audio and video streams, which is not covered.
*   **RTP De-packetization:** For many codecs, especially video codecs like H.264/HEVC, a dedicated RTP de-packetizer is necessary to correctly extract elementary stream data from RTP packets before feeding it to the decoder. The `codec_ctx.parse()` method has limitations.

### Running the Example

Once `pyav_example.py` is available in the `examples` directory and you have PyAV installed:

```bash
python examples/pyav_example.py rtsp://your_rtsp_server_url
```

For example:
```bash
python examples/pyav_example.py rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov
```

This will attempt to connect to the stream, decode a few frames from the video and/or audio tracks, and print information about them to the console.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

`aiortsp` is released under the MIT License.
```
