from binascii import hexlify
from time import time

import pytest

from aiortsp.rtcp.parser import SR, SDES, RR, RTCP, ts_to_ntp, ntp_to_ts, BYE


@pytest.mark.parametrize('data, klasses, alt', [
    ('80c8000677ae8d65e051bc2bea33b0001fa8034c0000000000000000', [SR], None),
    ('81c8000c5d931534dd3ac1b061d9c00000084f8000000d4c00084f8001932db40000000100000000000000000000000000000000', [SR], None),
    ('81ca000477ae8d650106756e6b6e6f7700000000', [SDES], None),
    ('81c9000730f5fb2730f5fb27000000000000726600000c0abc3ffbdb00030e42', [RR], None),
    ('81c9000730f5fb2730f5fb27000000000000726600000c0abc3ffbdb00030e4281ca000477ae8d650106756e6b6e6f7700000000', [RR, SDES], None),
    ('81cb0001166ae287', [BYE], None),

    # Padded
    ('a1ca000577ae8d650106756e6b6e6f770000000000000004', [SDES], '81ca000477ae8d650106756e6b6e6f7700000000'),
])
def test_rtcp_parse(data, klasses, alt):
    b = bytearray.fromhex(data)
    res = RTCP.unpack(b)

    assert [a.__class__ for a in res.packets] == klasses

    for k in klasses:
        assert isinstance(res.get(k.pt), k)

    # repack
    b2 = bytes(res)
    assert hexlify(b2).decode().lower() == (alt or data)

    # Just make sure the representation is not crashing
    print(res)


def test_ntp_to_time():
    t = 1554467594.1005
    n1, n2 = ts_to_ntp(t)
    assert t == ntp_to_ts(n1, n2)
