import pytest

from aiortsp.rtsp.parser import RTSPResponse, RTSPParser
from aiortsp.rtsp.session import RTSPMediaSession

CASES = [
    (1553609305.123, '20190326T140825.123Z'),
    (1553609305.12, '20190326T140825.12Z'),
    (1553609305.1, '20190326T140825.1Z'),
    (1553609305, '20190326T140825Z'),
]

@pytest.mark.parametrize('ref, exp', CASES)
def test_ts_to_clock(ref, exp):
    assert RTSPMediaSession.ts_to_clock(ref) == exp

@pytest.mark.parametrize('format', [
    'clock={}-',
    ' clock={}- ',
    ' clock ={} -',
    ' clock = {} -',
    ' clock =     {} -',
    ' clock = {} - 20190326T140828Z',
])
@pytest.mark.parametrize('exp, value', CASES)
def test_ts_to_clock(format, exp, value):
    resp = RTSPResponse()
    resp.headers = {
        'range': format.format(value)
    }
    assert RTSPMediaSession.response_to_ts(resp, None) == exp


def test_response_to_ts():

    parser = RTSPParser()

    resps = list(parser.parse(b"""RTSP/1.0 200 OK\r
CSeq: 4\r
Session: FD8A666F\r
Range: clock=20180101T010203.045Z-\r
RTP-Info: url=rtsp://192.168.1.98/axis-media/media.amp/trackID=1;seq=44350;rtptime=31576935\r
Date: Wed, 30 Sep 2020 20:08:49 GMT\r
\r
"""))

    assert len(resps) == 1
    assert RTSPMediaSession.response_to_ts(resps[0], 1) == 1514768523.045