"""
RTP Packet parsing
"""
from __future__ import annotations

from struct import Struct
from typing import Optional

_VERSION_MASK = 0xC000
_P_MASK = 0x2000
_X_MASK = 0x1000
_CC_MASK = 0x0F00
_M_MASK = 0x0080
_PT_MASK = 0x007F
_VERSION_SHIFT = 14
_P_SHIFT = 13
_X_SHIFT = 12
_CC_SHIFT = 8
_M_SHIFT = 7
_PT_SHIFT = 0

VERSION = 2


class RTP:
    """
    Real-Time Transport Protocol packet
    """

    hdr_struct = Struct("!HHII")

    def __init__(self, data: bytes):
        """
        :param data: Full RTP packet bytes
        """
        self._data = memoryview(data)
        self._new_data: Optional[bytes] = None
        self._type, self.seq, self.ts, self.ssrc = self.hdr_struct.unpack(self._data[:12])
        self._cc: int = None  # type: ignore

    def clone(self) -> RTP:
        # pylint: disable=protected-access
        """
        :return: RTP packet copy
        """
        clone = RTP(self._data)
        clone._new_data = self._new_data
        clone._cc = self._cc
        return clone

    @property
    def v(self) -> int:
        """
        :return: RTP version number
        """
        return (self._type & _VERSION_MASK) >> _VERSION_SHIFT

    @v.setter
    def v(self, ver: int) -> None:
        """
        :param ver: version number to set
        """
        self._type = (ver << _VERSION_SHIFT) | (self._type & ~_VERSION_MASK)

    @property
    def p(self) -> bool:
        """
        If the padding bit is set, the packet contains one or more
        additional padding octets at the end which are not part of the
        payload.

        :return: True if padding bit is set
        """
        return bool((self._type & _P_MASK) >> _P_SHIFT)

    @p.setter
    def p(self, p: bool) -> None:
        """
        Set padding bit

        :param p: padding bit enabled
        """
        self._type = (bool(p) << _P_SHIFT) | (self._type & ~_P_MASK)

    @property
    def x(self) -> bool:
        """
        If the extension bit is set, the fixed header MUST be followed by
        exactly one header extension.

        :return: True if extension bit is set
        """
        return bool((self._type & _X_MASK) >> _X_SHIFT)

    @x.setter
    def x(self, x: bool) -> None:
        """
        Setter for extension bit.

        :param x: extension bit enabled
        """
        self._type = (bool(x) << _X_SHIFT) | (self._type & ~_X_MASK)

    @property
    def cc(self) -> int:
        """
        The CSRC count contains the number of CSRC identifiers that follow
        the fixed header.

        :return: Number of CSRC headers
        """
        if self._cc is None:
            self._cc = (self._type & _CC_MASK) >> _CC_SHIFT
        return self._cc

    @cc.setter
    def cc(self, cc: int) -> None:
        """
        Setter for CC field

        :param cc: Number of CSRC headers
        """
        self._cc = cc
        self._type = (cc << _CC_SHIFT) | (self._type & ~_CC_MASK)

    @property
    def m(self) -> bool:
        """
        The interpretation of the marker is defined by a profile.  It is
        intended to allow significant events such as frame boundaries to
        be marked in the packet stream.

        :return: True if marker bit is set
        """
        return bool((self._type & _M_MASK) >> _M_SHIFT)

    @m.setter
    def m(self, m: bool) -> None:
        """
        Setter for marker bit.

        :param m: Marker enabled
        """
        self._type = (bool(m) << _M_SHIFT) | (self._type & ~_M_MASK)

    @property
    def pt(self) -> int:
        """
        This field identifies the format of the RTP payload and determines
        its interpretation by the application.

        :return: payload type
        """
        return (self._type & _PT_MASK) >> _PT_SHIFT

    @pt.setter
    def pt(self, m: int) -> None:
        """
        Setter for payload_type field.

        :param m: payload type
        """
        self._type = (m << _PT_SHIFT) | (self._type & ~_PT_MASK)

    @property
    def data(self) -> bytes:
        """
        Getter for payload data.

        :return: payload data
        """
        if self._new_data:
            return self._new_data
        return self._data[12 + self.cc * 4 :]

    @data.setter
    def data(self, value: bytes) -> None:
        """
        Setter for payload data.

        :param value: new payload
        """
        self._new_data = value

    def __len__(self):
        if self._new_data is None:
            return len(self._data)
        return 12 + self.cc * 4 + len(self._new_data)

    def __bytes__(self):
        return b"".join([self.pack_hdr(), self.csrc, self.data])

    @property
    def csrc(self) -> bytes:
        """
        The CSRC list identifies the contributing sources for the payload
        contained in this packet.

        :return: bytes for CSRC list
        """
        return self._data[12 : 12 + self.cc * 4]

    def pack_hdr(self) -> bytes:
        """
        Pack RTP header and data

        :return: resulting RTP packet bytes
        """
        return self.hdr_struct.pack(self._type, self.seq, self.ts, self.ssrc)
