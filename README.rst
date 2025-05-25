RTSP Library for asyncio
========================

.. image:: https://travis-ci.com/marss/aiortsp.svg?branch=master
    :target: https://travis-ci.com/marss/aiortsp

.. image:: https://coveralls.io/repos/github/marss/aiortsp/badge.svg?branch=master
    :target: https://coveralls.io/github/marss/aiortsp?branch=master

This is a very simple asyncio library for interacting with an
RTSP server, with basic RTP/RTCP support.

The intended use case is to provide a pretty low level control
of what happens at RTSP connection level, all in python/asyncio.

This library does not provide any decoding capability,
it is up to the client to decide what to do with received RTP packets.

One could easily decode using `OpenCV <https://pypi.org/project/opencv-python/>`_
or `PyAV <https://pypi.org/project/av/>`_, or not at all depending on the intended
use.

See ``examples`` for how to use the lib internals, butfor quick usage:

.. code-block:: python3

    import asyncio
    from aiortsp.rtsp.reader import RTSPReader

    async def main():
        # Open a reader (which means RTSP connection, then media session)
        async with RTSPReader('rtsp://cam/video.sdp') as reader:
            # Iterate on RTP packets
            async for pkt in reader.iter_packets():
                print('PKT', pkt.seq, pkt.pt, len(pkt))

    asyncio.run(main())

Decoding Video and Audio with PyAV
----------------------------------

``aiortsp`` can be used in conjunction with libraries like PyAV_ to decode video and audio streams received from an RTSP server. PyAV provides Python bindings for the FFmpeg_ libraries.

.. _PyAV: https://pyav.org/
.. _FFmpeg: https://ffmpeg.org/

Prerequisites
~~~~~~~~~~~~~

You need to install PyAV and its dependencies. FFmpeg is a core dependency.

.. code-block:: bash

    pip install av

Please refer to the `PyAV installation documentation <https://pyav.org/docs/stable/overview/installation.html>`_ for detailed instructions on installing FFmpeg for your operating system.

Example Overview
~~~~~~~~~~~~~~~~

The ``examples/pyav_example.py`` script (to be provided in a subsequent step) demonstrates how to:
1.  Connect to an RTSP server using ``aiortsp``.
2.  Set up one or more media streams (e.g., video and audio).
3.  For each stream, use PyAV's ``CodecContext`` to decode the incoming RTP packets.
4.  Log basic information about the decoded frames.

This example focuses on showing the integration and is not a full-fledged media player.

Key Code Snippets
~~~~~~~~~~~~~~~~~

Here are some illustrative snippets showing the core concepts:

**1. Setting up ``RTSPMediaSession`` for multiple streams:**

.. code-block:: python

    # In main_decoder_loop from examples/pyav_example.py (conceptual)
    from aiortsp.rtsp.session import RTSPMediaSession
    from aiortsp.transport import transport_for_scheme

    # ... (RTSPConnection setup as p_url, conn, logger) ...

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

**2. Per-stream handler (``StreamDecoder`` class structure):**

.. code-block:: python

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
        def __init__(self, media_type, rtpmap_info, fmtp_params): # fmtp_params is a dict
            self.media_type = media_type
            self.rtpmap = rtpmap_info # dict from SDP parsing
            self.fmtp_params = fmtp_params # dict from SDP parsing
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

            if self.codec_ctx.name == 'h264' and 'sprop-parameter-sets' in self.fmtp_params:
                sprop = self.fmtp_params['sprop-parameter-sets']
                sps_pps_list = sprop.split(',')
                extradata = bytearray()
                for nal_b64 in sps_pps_list:
                    try:
                        nal_bytes = base64.b64decode(nal_b64)
                        extradata.extend(b'\x00\x00\x00\x01' + nal_bytes) # Prepend Annex B start code
                    except binascii.Error:
                        # Log or handle Base64 decoding error
                        continue 
                if extradata:
                    self.codec_ctx.extradata = bytes(extradata)
            
            elif self.codec_ctx.name == 'aac' and 'config' in self.fmtp_params:
                aac_config_hex = self.fmtp_params['config']
                try:
                    self.codec_ctx.extradata = binascii.unhexlify(aac_config_hex)
                except binascii.Error:
                    # Log or handle hex decoding error
                    pass


        def handle_rtp_packet(self, rtp_packet):
            if not self.codec_ctx or self.decoded_frames_count >= 5: # Decode a few frames for example
                return
            try:
                # WARNING: codec_ctx.parse() does NOT handle H.264 FU-A fragmentation.
                av_packets = self.codec_ctx.parse(rtp_packet.data)
                for av_packet in av_packets:
                    frames = self.codec_ctx.decode(av_packet)
                    for frame in frames:
                        self.decoded_frames_count += 1
                        print(f"Decoded {self.media_type} frame {self.decoded_frames_count}: PTS={frame.pts}")
                        if self.decoded_frames_count >= 5: break
            except av.AVError as e:
                # Handle decoding errors, e.g., if e.errno == errno.EAGAIN (needs more data)
                # or if str(e) contains "Resource temporarily unavailable"
                pass 

**3. Subscribing handlers to transports:**

.. code-block:: python

    # In main_decoder_loop, after media_session.setup()
    # conceptual from examples/pyav_example.py

    stream_decoders = {}
    if media_session.is_setup:
        for media_type, transport_instance in media_session.transports.items():
            media_description = media_session.sdp.get_media(media_type) 
            if media_description:
                rtpmap_info = media_description['attributes'].get('rtpmap') # This is a dict
                
                # Assuming fmtp is also parsed into a dictionary by sdp.get_media or similar
                fmtp_params = media_description['attributes'].get('fmtp', {}) 
                # If fmtp is a string, it needs parsing:
                # fmtp_line = media_description['attributes'].get('fmtp_str', '')
                # fmtp_params = {}
                # if fmtp_line:
                #    parts = fmtp_line.split(';')
                #    for part in parts[1:]: # Skip format number
                #        if '=' in part:
                #            key, value = part.split('=',1)
                #            fmtp_params[key.strip().lower()] = value.strip()


                if rtpmap_info:
                    decoder = StreamDecoder(media_type, rtpmap_info, fmtp_params)
                    if decoder.codec_ctx:
                        transport_instance.subscribe(
                            rtp_handler=decoder.handle_rtp_packet
                            # rtcp_handler=decoder.handle_rtcp_packet, (optional)
                            # close_handler=decoder.handle_closed (optional)
                        )
                        stream_decoders[media_type] = decoder

How it Works
~~~~~~~~~~~~

1.  **SDP (Session Description Protocol):** When ``media_session.setup()`` is called, ``aiortsp`` sends a ``DESCRIBE`` request. The server responds with an SDP description detailing available media streams, including encoding formats (e.g., H.264, AAC), RTP mapping (``rtpmap``), and format-specific parameters (``fmtp``).
2.  **Extradata:** Some codecs, like H.264 and AAC, require "extradata" for decoder initialization.
    *   For H.264, this is typically SPS (Sequence Parameter Set) and PPS (Picture Parameter Set), often found in the ``sprop-parameter-sets`` field of ``a=fmtp`` line.
    *   For AAC, an ``AudioSpecificConfig`` (often in the ``config`` field of ``a=fmtp``) is needed.
    The ``StreamDecoder`` example attempts to parse this from SDP and set it on ``codec_ctx.extradata``.
3.  **Packet Processing:**
    *   ``aiortsp`` receives RTP packets.
    *   The subscribed ``handle_rtp_packet`` in ``StreamDecoder`` gets the RTP payload.
    *   ``codec_ctx.parse(rtp_packet.data)`` attempts to group RTP data into Access Units.
    *   ``codec_ctx.decode(av_packet)`` decodes these units into frames.

Important Considerations & Limitations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*   **H.264 RTP Packetization (FU-A):** A significant challenge with H.264 over RTP is that large NAL units (like I-frames) are often fragmented across multiple RTP packets using Fragmentation Units (FU-A). The basic ``codec_ctx.parse()`` in PyAV **does not handle reassembly of FU-A fragmented NAL units**. For robust H.264 decoding, an RTP de-packetizer for H.264 is required to reconstruct complete NAL units before passing them to PyAV.
*   **Codec Support:** Decoding capability depends on the codecs supported by the FFmpeg build used by PyAV.
*   **Error Handling & Timestamps:** The example provides basic error handling. Production applications need more sophisticated mechanisms for network issues, decoding errors, and proper handling of Presentation Timestamps (PTS) for A/V synchronization.
*   **RTP De-packetization:** For many codecs, a dedicated RTP de-packetizer is often necessary.

Running the Example
~~~~~~~~~~~~~~~~~~~

Once ``examples/pyav_example.py`` is available and PyAV is installed:

.. code-block:: bash

    python examples/pyav_example.py rtsp://your_rtsp_server_url

For example:

.. code-block:: bash

    python examples/pyav_example.py rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov

This will attempt to connect, decode a few frames, and print information to the console.
