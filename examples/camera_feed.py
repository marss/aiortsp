import asyncio
import logging

from aiortsp.rtsp.reader import RTSPReader

URL = f'rtspt://admin:bpa2017@192.168.0.82:554/1/1'
MEDIA_TYPES=['video', 'audio']
VIDEO_FILE = 'cam_video.h264'
AUDIO_FILE = 'cam_audio.pcm'

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RTSPLogger')
logger.propagate = True

def nal_decode(data, video_file):
    '''
    5.3.  NAL Unit Header Usage

       The structure and semantics of the NAL unit header were introduced in
       Section 1.3.  For convenience, the format of the NAL unit header is
       reprinted below:

          +---------------+
          |0|1|2|3|4|5|6|7|
          +-+-+-+-+-+-+-+-+
          |F|NRI|  Type   |
          +---------------+
    '''
    FNRI_MASK = 0xE0
    NAL_TYPE_MASK = 0x1F
    FU_START_BIT_MASK = 0x80
    NAL_START= b'\x00\x00\x00\x01'
    nal_type = (data[0] & NAL_TYPE_MASK)
    '''
    https://datatracker.ietf.org/doc/html/rfc6184#section-5.3

    NAL Unit  Packet    Packet Type Name               Section
    Type      Type
    -------------------------------------------------------------
    0        reserved                                     -
    1-23     NAL unit  Single NAL unit packet             5.6
    24       STAP-A    Single-time aggregation packet     5.7.1
    25       STAP-B    Single-time aggregation packet     5.7.1
    26       MTAP16    Multi-time aggregation packet      5.7.2
    27       MTAP24    Multi-time aggregation packet      5.7.2
    28       FU-A      Fragmentation unit                 5.8
    29       FU-B      Fragmentation unit                 5.8
    30-31    reserved                                     -
    '''
    # Single NAL Unit Packets
    if nal_type in range(1, 24):
        logger.debug("single NAL unit packet")
        video_file.write(NAL_START)
        video_file.write(data)
    # FU-A
    elif nal_type == 28:
        logger.debug("FU-A packet")

        '''
        The FU header has the following format:

              +---------------+
              |0|1|2|3|4|5|6|7|
              +-+-+-+-+-+-+-+-+
              |S|E|R|  Type   |
              +---------------+

           S:     1 bit
                  When set to one, the Start bit indicates the start of a
                  fragmented NAL unit.  When the following FU payload is not the
                  start of a fragmented NAL unit payload, the Start bit is set
                  to zero.

           E:     1 bit
                  When set to one, the End bit indicates the end of a fragmented
                  NAL unit, i.e., the last byte of the payload is also the last
                  byte of the fragmented NAL unit.  When the following FU
                  payload is not the last fragment of a fragmented NAL unit, the
                  End bit is set to zero.

           R:     1 bit
                  The Reserved bit MUST be equal to 0 and MUST be ignored by the
                  receiver.

           Type:  5 bits
                  The NAL unit payload type as defined in Table 7-1 of [1].

           The value of DON in FU-Bs is selected as described in Section 5.5.

              Informative note: The DON field in FU-Bs allows gateways to
              fragment NAL units to FU-Bs without organizing the incoming NAL
              units to the NAL unit decoding order.
        '''
        if (data[1] & FU_START_BIT_MASK):
            logger.debug("FU-A packet start!")
            video_file.write(NAL_START)
            video_file.write(bytes([(data[0] & FNRI_MASK) | (data[1] & NAL_TYPE_MASK)]))
        video_file.write(data[2:])
    # STAP-A, STAP-B
    elif nal_type in [24, 25]:
        logger.debug("STRAP A/B packet")
        # https://datatracker.ietf.org/doc/html/rfc6184#section-5.7.1
        offset = 1
        while offset < len(data):
            nal_size = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            video_file.write(NAL_START)
            video_file.write(data[offset:offset+nal_size])
            offset += nal_size
    elif nal_type in [26, 27]:  # MTAP16, MTAP24
        logger.debug("MTAP16 MTAP24 packet (ignored)")
        # Multi-time aggregation packet (MTAP): aggregates NAL units with
        # potentially differing NALU-times.  Two different MTAPs are
        # defined, differing in the length of the NAL unit timestamp offset.
        # TODO
        pass

async def main():
    async with RTSPReader(URL, media_types=MEDIA_TYPES, log_level=logging.DEBUG) as reader:
        with open(VIDEO_FILE, 'wb') as video_file:
            with open(AUDIO_FILE, 'wb') as audio_file:
                count=0
                async for media_type, pkt in reader.iter_packets():
                    print(f'{media_type} {pkt.pt}')
                    if media_type == 'video':
                        nal_decode(pkt.data, video_file)
                    elif media_type == 'audio':
                        audio_file.write(pkt.data)
                    else:
                        print(f'unsupported {media_type} {pkt.pt}')
                    count += 1
                    if count > 100:
                        break


asyncio.run(main())
