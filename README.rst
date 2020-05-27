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
