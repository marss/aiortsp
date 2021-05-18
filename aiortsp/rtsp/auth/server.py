"""
Authentication on server side
"""
import hashlib
import random
import string
import weakref
from base64 import b64decode
from time import time
from typing import Any, Dict, Mapping

from aiortsp.rtsp.parser import RTSPRequest

from .digest import DigestClientAuth, parse_digest_header

DEFAULT_AUTH = ["basic", "digest"]
DEFAULT_REALM = "aiortsp_authentication"


def rand_string(length: int) -> str:
    return "".join(
        [random.choice(string.ascii_lowercase + string.digits) for _ in range(length)]
    )


class ServerAuth:
    """
    Implementation of a authentication server.
    """

    def __init__(
        self,
        credentials: Dict[str, str],
        max_reuse: int = None,
        protocols: list = DEFAULT_AUTH,
    ):
        """
        :param credentials: a dict of username: password mappings
        :param max_reuse: if provided, force nonce change after X authentications
        """
        self.credentials = credentials
        self.max_reuse = max_reuse
        self.clients: Mapping[Any, dict] = weakref.WeakKeyDictionary()
        self.protocols = protocols
        assert all(
            p in DEFAULT_AUTH for p in protocols
        ), f"invalid protocols {protocols}"
        self.secret = rand_string(32)

    def get_nonce(self) -> str:
        """Build a nonce"""
        return hashlib.sha256(
            (str(time()) + ":" + self.secret).encode("utf-8")
        ).hexdigest()

    def get_or_create_context(self, client: Any) -> dict:
        """
        Given a "client" (whatever that is), return an authentication context.
        """
        if client not in self.clients:
            self.clients[client] = {"used": 0, "nonce": self.get_nonce()}

        return self.clients[client]

    def build_headers(self, client) -> dict:
        """
        Return authentication headers for a failed or missing authentication
        """
        auths = []

        if "basic" in self.protocols:
            auths.append(f'Basic realm="{DEFAULT_REALM}"')

        if "digest" in self.protocols:
            ctx = self.get_or_create_context(client)
            params = {"realm": DEFAULT_REALM, "nonce": ctx["nonce"]}
            opts = ", ".join(f'{k}="{v}"' for k, v in params.items())
            auths.append(f"Digest {opts}")

        return {"WWW-Authenticate": auths}

    def digest_auth(self, client, header, request) -> bool:
        """
        Tell if provided digest authorization is good enough
        """
        ctx = self.get_or_create_context(client)

        fields = parse_digest_header(header[7:])

        # is the amount of reuse for the nonce reached?
        if self.max_reuse and ctx["used"] == self.max_reuse:
            ctx["nonce"] = self.get_nonce()
            ctx["used"] = 0
            return False

        algorithm = fields.get("algorithm", "MD5").upper()
        realm = fields.get("realm")
        nonce = fields.get("nonce")
        uri = fields.get("uri")
        username = fields.get("username")

        # is the nonce or opaque different?
        if ctx["nonce"] != nonce:
            return False

        if realm != DEFAULT_REALM:
            return False

        if not uri:
            return False

        # Now just apply same logic as client: should get the response.

        if username not in self.credentials:
            return False

        hash_digest = DigestClientAuth._digest_function(algorithm)

        A1 = "%s:%s:%s" % (username, realm, self.credentials[username])
        A2 = "%s:%s" % (request.method, uri)

        HA1 = hash_digest(A1)
        HA2 = hash_digest(A2)

        # Direct response as per RFC 2069 - 2.1.1
        response = hash_digest(f"{HA1}:{nonce}:{HA2}")

        return response == fields.get("response")

    def basic_auth(self, header: str) -> bool:
        """
        Tell if provided basic authorization is good enough
        """
        try:
            username, password = b64decode(header[6:].strip()).decode().split(":", 1)
            return self.credentials[username] == password
        except Exception as ex:
            # TODO Probably want to log something?
            return False

    def handle_auth(self, client: Any, request: RTSPRequest) -> bool:
        """
        Make sure the authentication is correct.
        Return an unauthorized otherwise
        """
        auth = request.headers.get("authorization", "")

        if auth.startswith("Digest ") and "digest" in self.protocols:
            success = self.digest_auth(client, auth, request)
        elif auth.startswith("Basic ") and "basic" in self.protocols:
            success = self.basic_auth(auth)
        else:
            # Either no header, or invalid protocol
            success = False

        if not success:
            client.send_response(
                request=request,
                code=401,
                msg="Unauthorized",
                headers=self.build_headers(client),
            )

        return success
