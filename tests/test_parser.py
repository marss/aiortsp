import pytest

from aiortsp.rtsp.parser import RTSPParser


DATA = [
    # Very dumb one
    (b"""RTSP/1.0 200 OK\r\nCSeq: 0\r\n\r\n""", [('response', (200, 0, 0, None))]),

    # Response to play
    (b"""RTSP/1.0 200 OK\r
Range: clock=20190315T043720.003Z-\r
RTP-Info: url=rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback;ssrc=871954036;seq=60290;rtptime=0\r
CSeq: 3\r
Session: 35765835\r
X-RtspClientVersion: 5.7\r
\r\n""", [('response', (200, 3, 0, None))]),

    # SDP Answer
    (b"""RTSP/1.0 200 OK\r
Content-Type: application/sdp\r
Content-Length: 302\r
CSeq: 1\r
Session: 35765835\r
X-RtspClientVersion: 5.7\r
\r
v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
m=video 0 RTP/AVP 96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96 packetization-mode=1; profile-level-id=420029; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA==\r
a=control:rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback\r
""", [('response', (200, 1, 302, """v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
m=video 0 RTP/AVP 96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96 packetization-mode=1; profile-level-id=420029; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA==\r
a=control:rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback\r
"""))]),

    # Data not ending with an EOL
    (b"""RTSP/1.0 462 Destination Unreachable\r
Content-Type: text/plain\r
Content-Length: 110\r
CSeq: 2\r
Session: 64118488;timeout=90\r
X-RtspClientVersion: 5.7\r
\r
Client requested end point already in use for camera 00000001-0000-babe-0000-accc8e000aa7 in session 26378381.RTSP/1.0 200 OK\r\nCSeq: 3\r\n\r\n""", [
        ('response', (462, 2, 110, 'Client requested end point already in use for camera 00000001-0000-babe-0000-accc8e000aa7 in session 26378381.')),
        ('response', (200, 3, 0, None)),
    ]),

    # Multiple Answers
    (b"""RTSP/1.0 200 OK\r\nCSeq: 0\r\n\r\nRTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n""", [
        ('response', (200, 0, 0, None)),
        ('response', (404, 1, 0, None)),
    ]),

    # Multiple Answers, with extra lines in between! (not fully RFC compliant...)
    (b"""RTSP/1.0 200 OK\r\nCSeq: 0\r\n\r\n\r\nRTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n""", [
        ('response', (200, 0, 0, None)),
        ('response', (404, 1, 0, None)),
    ]),

    # Multiple binary
    (b"""$\000\000\003iii$\001\000\007Hello!!""", [
        ('binary', (0, b'iii')),
        ('binary', (1, b'Hello!!')),
    ]),

    # Binary followed by incomplete Response header
    (b"""$\000\000\003iiiRTSP/1.0 200 O""", [
        ('binary', (0, b'iii')),
    ]),

    # Answer and binary
    (b"""RTSP/1.0 200 OK\r\nCSeq: 0\r\n\r
$\000\000\003iii\r\n$\001\000\007Hello!!RTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n""", [
        ('response', (200, 0, 0, None)),
        ('binary', (0, b'iii')),
        ('binary', (1, b'Hello!!')),
        ('response', (404, 1, 0, None)),
    ]),

    # Announce incoming
    (b"""ANNOUNCE rtsp://foo.com/bar.avi RTSP/1.0\r
CSeq: 10\r
Session: 12345678\r
Require: method.announce\r
Event-Type: End-Of-Stream\r
Range: npt=10-100\r
RTP-Info: url= rtsp://foo.com/bar.avi/streamid=0; seq=456,\r
  url= rtsp://foo.com/bar.avi/streamid=1; seq=789\r
Content-Type: text/parameters\r
\r
""", [
        ('request', ('ANNOUNCE', 'rtsp://foo.com/bar.avi', 10)),
    ]),
]


@pytest.mark.parametrize('data, objs', DATA)
def test_simple_response(data, objs):

    parser = RTSPParser()

    resps = list(parser.parse(data))

    assert len(resps) == len(objs)

    for i in range(len(objs)):
        resp = resps[i]
        type_ = objs[i][0]

        assert resp.type == type_

        if type_ == 'response':
            status, cseq, length, content = objs[i][1]
            assert resp.status == status
            assert resp.cseq == cseq
            assert resp.content_length == length
            if content:
                assert resp.content == content
        elif type_ == 'binary':
            id_, data = objs[i][1]
            assert resp.id == id_
            assert resp.length == len(data)
            assert resp.data == data
        elif type_ == 'request':
            method, url, cseq = objs[i][1]
            assert resp.method == method
            assert resp.request_url == url
            assert resp.cseq == cseq


@pytest.mark.parametrize('data, objs', DATA)
def test_chunk_response(data, objs):

    parser = RTSPParser()

    resps = []

    for chunk_idx in range(1 + len(data) // 4):
        resps.extend(list(parser.parse(data[chunk_idx*4:(chunk_idx+1)*4])))

    assert len(resps) == len(objs)

    for i in range(len(objs)):
        resp = resps[i]
        type_ = objs[i][0]

        assert resp.type == type_

        if type_ == 'response':
            status, cseq, length, content = objs[i][1]
            assert resp.status == status
            assert resp.cseq == cseq
            assert resp.content_length == length
            if content:
                assert resp.content == content
        elif type_ == 'binary':
            id_, data = objs[i][1]
            assert resp.id == id_
            assert resp.length == len(data)
            assert resp.data == data
        elif type_ == 'request':
            method, url, cseq = objs[i][1]
            assert resp.method == method
            assert resp.request_url == url
            assert resp.cseq == cseq
