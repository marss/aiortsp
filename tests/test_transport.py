"""
Testing for transport and associated tools
"""

import pytest

from aiortsp.transport.base import RTPTransport


@pytest.mark.parametrize(
    "header, expected",
    [
        (
            'RTP/AVP;multicast;ttl=127;mode="PLAY"',
            [
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "multicast",
                    "ttl": 127,
                    "mode": "PLAY",
                },
            ],
        ),
        (
            'RTP/AVP;unicast;client_port=3456-3457;server_port=6543-6544;mode="PLAY"',
            [
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "unicast",
                    "client_port": {"rtp": 3456, "rtcp": 3457},
                    "server_port": {"rtp": 6543, "rtcp": 6544},
                    "mode": "PLAY",
                },
            ],
        ),
        (
            'RTP/AVP;multicast;ttl=127;mode="PLAY",'
            'RTP/AVP;unicast;client_port=3456-3457;mode="PLAY"',
            [
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "multicast",
                    "ttl": 127,
                    "mode": "PLAY",
                },
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "unicast",
                    "client_port": {"rtp": 3456, "rtcp": 3457},
                    "mode": "PLAY",
                },
            ],
        ),
        (
            'RTP/AVP;multicast;ttl=127;mode="PLAY",\n'
            'RTP/AVP;unicast;client_port=3456-3457;mode="PLAY"',
            [
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "multicast",
                    "ttl": 127,
                    "mode": "PLAY",
                },
                {
                    "transport": "RTP",
                    "profile": "AVP",
                    "protocol": "UDP",
                    "delivery": "unicast",
                    "client_port": {"rtp": 3456, "rtcp": 3457},
                    "mode": "PLAY",
                },
            ],
        ),
    ],
)
def test_transport_header_parsing(header, expected):
    """test that transport header is parsed correctly"""
    assert RTPTransport.parse_transport_fields(header) == expected
