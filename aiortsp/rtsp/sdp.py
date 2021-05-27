"""
 Session Description - RFC 4566
 Very basic SDP parser
 ---------------------------------------------------------------------------------------
 type_    Dictionary key          Format of the value
 ======  ======================  =======================================================
 v       "protocol_version"      version_number
 o       "origin"                ("user", session_id, session_version, "net_type",
                                    "addr_type", "addr")
 s       "sessionname"           "session name"
 t & r   "time"                  (starttime, stoptime, [repeat,repeat, ...])
                                    where repeat = (interval,duration,[offset,offset])
 a       "attribute"             "value of attribute"
 b       "bandwidth"             (mode, bitspersecond)
 i       "information"           "value"
 e       "email"                 "email-address"
 u       "URI"                   "uri"
 p       "phone"                 "phone-number"
 c       "connection"            ("net_type", "addr_type", "addr", ttl, groupsize)
 z       "timezone adjustments"  [(adj-time,offset), (adj-time,offset), ...]
 k       "encryption"            ("method","value")
 m       "media"                 [media-description, media-description, ... ]
                                     see next table for media description structure
 ======  ======================  =======================================================
"""
from time import time
from typing import Optional

import sdp_transform


class SDP:
    """
    SDP Parser class.
    Takes an sdp content as an input and split it into various sections,
    including the different available medias.
    """

    def __init__(self, data: str):
        super().__init__()
        self.content = sdp_transform.parse(data)

        for media in self.content.get("media", []):
            for fmtp in media.get("fmtp", []):
                self.parse_fmtp(fmtp)

    def set_origin(
        self,
        username: str = None,
        session_id: int = None,
        session_version: int = None,
        net_type: str = "IN",
        addr_type: int = 4,
        unicast_address: str = "0.0.0.0",
    ):
        """
        Set origin content to SDP
        """
        now = int(time())
        self.content["origin"] = {
            "username": username or "-",
            "sessionId": session_id or now,
            "sessionVersion": session_version or now,
            "netType": net_type,
            "ipVer": addr_type,
            "address": unicast_address,
        }

    @staticmethod
    def parse_fmtp(fmtp: dict):
        """
        Parse fmtp config into individual options
        """
        options = {}
        for opt in fmtp.get("config", "").split(";"):
            if not opt.strip():
                # Empty, probably a wrong semicolon at the end...
                continue
            k, v = opt.split("=", 1)
            options[k.strip()] = v.strip()
        fmtp["options"] = options

    @staticmethod
    def mix_url_control(base: str, ctrl) -> str:
        """
        Given a base URL and a control attribute,
        build an URL to be used during SETUP.
        :param base: Base URL (either from user or returned in Content-Base)
        :param ctrl: Control attributes for given media (or global)
        :return: URL
        """
        if not ctrl or ctrl == "*":
            return base

        if ctrl.startswith("rtsp://"):
            return ctrl

        if not ctrl.startswith("/") and not base.endswith("/"):
            return base + "/" + ctrl

        return base + ctrl

    def get_media(self, media_type="video", media_idx=0):
        """
        Return the Nth media description matching requested type
        :param media_type:
        :param media_idx:
        :return:
        """
        current_idx = 0

        for media in self.content.get("media", []):
            if media["type"] != media_type:
                continue

            if current_idx < media_idx:
                current_idx += 1
                continue

            # Found it!
            return media

        return None

    def setup_url(self, base_url: str, media_type="video", media_idx=0) -> str:
        """
        Return the URL to be used for setup.
        :param base_url: (url requested or returned base url)
        :param media_type: audio|video|text|application|message
        :param media_idx: index if multiple medias are available
        :return: corrected URL
        """
        # Check global control
        base_url = self.mix_url_control(base_url, self.content.get("control"))

        # Look for media
        media = self.get_media(media_type, media_idx)
        if media:
            return self.mix_url_control(base_url, media.get("control"))

        # Not found in medias
        return base_url

    def media_clock_rate(self, media_type="video", media_idx=0) -> Optional[int]:
        """
        Return clock rate of given media
        """
        media = self.get_media(media_type, media_idx)
        if media and len(media["rtp"]) > 0:
            # Only one rtpmap in RTSP SDP
            return media["rtp"][0]["rate"]
        return None

    def media_payload_type(self, media_type="video", media_idx=0) -> Optional[int]:
        """
        Return clock rate of given media
        """
        media = self.get_media(media_type, media_idx)
        if media and len(media["rtp"]) > 0:
            # Only one rtpmap in RTSP SDP
            return media["rtp"][0]["payload"]
        return None

    def get_media_property(
        self, name: str, media_type="video", media_idx=0
    ) -> Optional[str]:
        """
        Get a property from a media fmtp config.

        :param name: Name of the property
        """
        media = self.get_media(media_type=media_type, media_idx=media_idx)
        if media and len("fmtp") > 0:
            return media["fmtp"][0]["options"].get(name)
        return None

    def guess_h264_props(self, media_idx=0) -> Optional[str]:
        """
        Try to guess H264 `sprop-parameter-sets`
        :param media_idx:
        :return: props string
        """
        return self.get_media_property("sprop-parameter-sets", media_idx=media_idx)

    def pack(self) -> str:
        """
        Build back the content as SDP
        """
        return sdp_transform.write(self.content)
