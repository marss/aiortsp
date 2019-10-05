import pytest

from aiortsp.rtsp.sdp import SDP


def test_sdp_simple():

    sdp = SDP("""v=0\r
o=- 0 0 IN IP4 0.0.0.0\r
s=\r
i=\r
c=IN IP4 0.0.0.0\r
t=0 0\r
m=video 0 RTP/AVP             96\r
a=rtpmap:96 H264/90000\r
a=fmtp:96  packetization-mode=1 ; profile-level-id=420029 ; sprop-parameter-sets=Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA==  \r
a=control:rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback\r
""")

    assert sdp['version'] == 0
    assert len(sdp['medias']) == 1
    med = sdp['medias'][0]

    assert med == sdp.get_media()

    assert med['protocol'] == 'RTP/AVP'

    attrs = med['attributes']

    # Control
    assert 'control' in attrs
    assert attrs['control'] == 'rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback'

    # fmtp
    assert 'fmtp' in attrs
    assert attrs['fmtp']['pt'] == 96
    assert attrs['fmtp']['sprop-parameter-sets'] == 'Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA=='
    assert attrs['fmtp']['profile-level-id'] == '420029'
    assert attrs['fmtp']['packetization-mode'] == '1'


def test_sdp_errors():
    """
    Add specially crafter errors which we want the parser to be robust about:
        - a trailing `;` at the end of `fmtp`
        - an empty line at the end and garbage
    """

    sdp = SDP("""v=0\r
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
""")

    assert sdp['version'] == 0
    assert len(sdp['medias']) == 1
    med = sdp['medias'][0]

    assert med == sdp.get_media()

    assert med['protocol'] == 'RTP/AVP'

    attrs = med['attributes']

    # Control
    assert 'control' in attrs
    assert attrs['control'] == 'rtsp://10.10.20.118:654/00000001-0000-babe-0000-accc8e000aa7/playback'

    # fmtp
    assert 'fmtp' in attrs
    assert attrs['fmtp']['pt'] == 96
    assert attrs['fmtp']['sprop-parameter-sets'] == 'Z0IAKeKQFoJNgScFAQXh4kRU,aM48gA=='
    assert attrs['fmtp']['profile-level-id'] == '420029'
    assert attrs['fmtp']['packetization-mode'] == '1'


@pytest.mark.parametrize('mix_ctrl, video_ctrl, req_base, expected_url', [
    # When no mix URL is provided but relative stream control is, mix base and stream
    ('*', 'stream=0', 'rtsp://foo/bar/', 'rtsp://foo/bar/stream=0'),
    # With a mix URL and relative stream control, base URL should be overwritten and aggregated
    ('rtsp://foo/toto/', 'stream=0', 'rtsp://foo/bar/', 'rtsp://foo/toto/stream=0'),

    # Same with absolute URLs
    ('*', 'rtsp://foo/snake/stream=0', 'rtsp://foo/bar/', 'rtsp://foo/snake/stream=0'),
    ('rtsp://foo/toto/', 'rtsp://foo/snake/stream=0', 'rtsp://foo/bar/', 'rtsp://foo/snake/stream=0'),

    # In some cases, a trailing backslash is not provided while a relative stream is...
    ('rtsp://foo/toto', 'stream=0', 'rtsp://foo/bar/', 'rtsp://foo/toto/stream=0'),
    ('*', 'stream=0', 'rtsp://foo/bar', 'rtsp://foo/bar/stream=0'),
])
def test_sdp_control_generic(mix_ctrl, video_ctrl, req_base, expected_url):
    sdp = SDP(f"""v=0\r
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
""")
    assert sdp.setup_url(req_base) == expected_url


