import pytest

from aiortsp.rtsp.sdp import SDP


def test_sdp_simple():

    sdp = SDP(
        """v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
m=video 0 RTP/AVP             96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96  packetization-mode=1 ; profile-level-id=420029 ; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA==  \r
a=control:rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback\r
"""
    )

    assert sdp.content["version"] == 0
    assert len(sdp.content["media"]) == 1
    med = sdp.content["media"][0]

    assert med == sdp.get_media()

    assert sdp.media_clock_rate() == 90000

    assert med["protocol"] == "RTP/AVP"

    # Control
    assert "control" in med
    assert (
        med["control"]
        == "rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback"
    )

    # fmtp
    assert "fmtp" in med
    assert len(med["fmtp"]) == 1
    assert med["fmtp"][0]["payload"] == 96
    assert (
        med["fmtp"][0]["options"]["sprop-parameter-sets"]
        == "Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA=="
    )
    assert med["fmtp"][0]["options"]["profile-level-id"] == "420029"
    assert med["fmtp"][0]["options"]["packetization-mode"] == "1"


def test_sdp_errors():
    """
    Add specially crafter errors which we want the parser to be robust about:
        - a trailing `;` at the end of `fmtp`
        - an empty line at the end and garbage
    """

    sdp = SDP(
        """v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
m=video 0 RTP/AVP             96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96  packetization-mode=1 ; profile-level-id=420029 ; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA== ; \r
a=control:rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback\r
hello=world\r
\r
"""
    )

    assert sdp.content["version"] == 0
    assert len(sdp.content["media"]) == 1
    med = sdp.content["media"][0]

    assert med == sdp.get_media()

    assert med["protocol"] == "RTP/AVP"

    # Control
    assert "control" in med
    assert (
        med["control"]
        == "rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback"
    )

    # fmtp
    assert "fmtp" in med
    assert len(med["fmtp"]) == 1
    assert med["fmtp"][0]["payload"] == 96
    assert sdp.media_payload_type() == 96
    assert (
        med["fmtp"][0]["options"]["sprop-parameter-sets"]
        == "Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA=="
    )
    assert med["fmtp"][0]["options"]["profile-level-id"] == "420029"
    assert med["fmtp"][0]["options"]["packetization-mode"] == "1"
    assert sdp.guess_h264_props() == "Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA=="


@pytest.mark.parametrize(
    "mix_ctrl, video_ctrl, req_base, expected_url",
    [
        # When no mix URL is provided but relative stream control is, mix base and stream
        ("*", "stream=0", "rtsp://foo/bar/", "rtsp://foo/bar/stream=0"),
        # With a mix URL and relative stream control, base URL should be overwritten and aggregated
        ("rtsp://foo/toto/", "stream=0", "rtsp://foo/bar/", "rtsp://foo/toto/stream=0"),
        # Same with absolute URLs
        (
            "*",
            "rtsp://foo/snake/stream=0",
            "rtsp://foo/bar/",
            "rtsp://foo/snake/stream=0",
        ),
        (
            "rtsp://foo/toto/",
            "rtsp://foo/snake/stream=0",
            "rtsp://foo/bar/",
            "rtsp://foo/snake/stream=0",
        ),
        # In some cases, a trailing backslash is not provided while a relative stream is...
        ("rtsp://foo/toto", "stream=0", "rtsp://foo/bar/", "rtsp://foo/toto/stream=0"),
        ("*", "stream=0", "rtsp://foo/bar", "rtsp://foo/bar/stream=0"),
    ],
)
def test_sdp_control_generic(mix_ctrl, video_ctrl, req_base, expected_url):
    sdp = SDP(
        f"""v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
a=control:{mix_ctrl}\r
m=video 0 RTP/AVP             96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96  packetization-mode=1 ; profile-level-id=420029 ; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA==  \r
a=control:{video_ctrl}\r
"""
    )
    assert sdp.setup_url(req_base) == expected_url


def test_multiple_media():
    sdp = SDP(
        """v=0
o=- 2890844256 2890842807 IN IP4 204.34.34.32
s=I came from a web page
t=0 0
a=sendonly
c=IN IP4 0.0.0.0
a=control:rtsp://video.com/movie/
m=video 8002 RTP/AVP 31
a=control:track1
a=rtpmap:31 H264/90000
a=fmtp:31 foo=bar;toto=42
m=audio 8004 RTP/AVP 3
a=control:track2
"""
    )
    assert sdp.get_media(media_type="video", media_idx=0)["payloads"] == 31
    assert sdp.get_media(media_type="audio", media_idx=0)["payloads"] == 3
    assert sdp.get_media(media_type="audio", media_idx=1) is None
    assert sdp.get_media(media_type="audio", media_idx=10) is None
    assert sdp.get_media(media_type="video", media_idx=1) is None

    assert sdp.guess_h264_props(media_idx=42) is None

    assert "a=rtpmap:31 H264/90000" in sdp.pack()

    sdp2 = SDP("")
    assert sdp2.media_clock_rate() is None
    assert sdp2.media_payload_type() is None

    assert sdp2.setup_url("rtsp://foo/bar") == "rtsp://foo/bar"

    sdp2.set_origin(username="toto")
    assert sdp2.content["origin"]["username"] == "toto"

    assert "o=toto" in sdp2.pack()


@pytest.mark.parametrize(
    "data",
    [
        # ALL SDP in RFC 2326
        """v=0
o=mhandley 2890844526 2890842807 IN IP4 126.16.64.4
s=SDP Seminar
i=A Seminar on the session description protocol
u=http://www.cs.ucl.ac.uk/staff/M.Handley/sdp.03.ps
e=mjh@isi.edu (Mark Handley)
c=IN IP4 224.2.17.12/127
t=2873397496 2873404696
a=recvonly
m=audio 3456 RTP/AVP 0
m=video 2232 RTP/AVP 31
m=whiteboard 32416 UDP WB
a=orient:portrait
""",
        """v=0
o=mhandley 2890844526 2890845468 IN IP4 126.16.64.4
s=SDP Seminar
i=A Seminar on the session description protocol
u=http://www.cs.ucl.ac.uk/staff/M.Handley/sdp.03.ps
e=mjh@isi.edu (Mark Handley)
c=IN IP4 224.2.17.12/127
t=2873397496 2873404696
a=recvonly
m=audio 3456 RTP/AVP 0
m=video 2232 RTP/AVP 31
""",
        """v=0
o=- 2890844526 2890842807 IN IP4 192.16.24.202
s=RTSP Session
m=audio 0 RTP/AVP 0
a=control:rtsp://audio.example.com/twister/audio.en
m=video 0 RTP/AVP 31
a=control:rtsp://video.example.com/twister/video
""",
        """v=0
o=- 2890844256 2890842807 IN IP4 172.16.2.93
s=RTSP Session
i=An Example of RTSP Session Usage
a=control:rtsp://foo/twister
t=0 0
m=audio 0 RTP/AVP 0
a=control:rtsp://foo/twister/audio
m=video 0 RTP/AVP 26
a=control:rtsp://foo/twister/video
""",
        """v=0
o=- 872653257 872653257 IN IP4 172.16.2.187
s=mu-law wave file
i=audio test
t=0 0
m=audio 0 RTP/AVP 0
a=control:streamid=0
""",
        """v=0
o=- 2890844526 2890842807 IN IP4 192.16.24.202
s=RTSP Session
m=audio 3456 RTP/AVP 0
a=control:rtsp://live.example.com/concert/audio
c=IN IP4 224.2.0.1/16
""",
        """v=0
o=- 2890844526 2890842807 IN IP4 192.16.24.202
s=RTSP Session
i=See above
t=0 0
m=audio 0 RTP/AVP 0
""",
        """v=0
o=camera1 3080117314 3080118787 IN IP4 195.27.192.36
s=IETF Meeting, Munich - 1
i=The thirty-ninth IETF meeting will be held in Munich, Germany
u=http://www.ietf.org/meetings/Munich.html
e=IETF Channel 1 <ietf39-mbone@uni-koeln.de>
p=IETF Channel 1 +49-172-2312 451
c=IN IP4 224.0.1.11/127
t=3080271600 3080703600
a=tool:sdr v2.4a6
a=type:test
m=audio 21010 RTP/AVP 5
c=IN IP4 224.0.1.11/127
a=ptime:40
m=video 61010 RTP/AVP 31
c=IN IP4 224.0.1.12/127
""",
        """v=0
o=- 2890844256 2890842807 IN IP4 204.34.34.32
s=I came from a web page
t=0 0
c=IN IP4 0.0.0.0
m=video 8002 RTP/AVP 31
a=control:rtsp://audio.com/movie.aud
m=audio 8004 RTP/AVP 3
a=control:rtsp://video.com/movie.vid
""",
        """v=0
o=- 2890844256 2890842807 IN IP4 204.34.34.32
s=I contain
i=<more info>
t=0 0
c=IN IP4 0.0.0.0
a=control:rtsp://example.com/movie/
m=video 8002 RTP/AVP 31
a=control:trackID=1
m=audio 8004 RTP/AVP 3
a=control:trackID=2
""",
    ],
)
def test_sdps(data):
    """
    Simple check it parses without problem all SDP from the RFC
    """
    sdp = SDP(data)
    sdp.pack()
