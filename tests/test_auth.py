from unittest.mock import Mock

import pytest

from aiortsp.rtsp.auth import BasicClientAuth, DigestClientAuth, ServerAuth
from aiortsp.rtsp.parser import RTSPRequest, RTSPResponse


@pytest.mark.parametrize(
    "user, passwd, method, url, req, repl",
    [
        (
            "root",
            "admin123",
            "DESCRIBE",
            "rtsp://cam/axis-media/media.amp",
            {
                # Challenge
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
            },
            {
                # Response
                "username": "root",
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
                "uri": "rtsp://cam/axis-media/media.amp",
                "response": "7daaf0f4e40fdff42cff28260f37914d",
            },
        ),
        (
            "test",
            "test123",
            "DESCRIBE",
            "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
            {
                # Challenge
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "opque": "0bd45fa6a89e4873a4c80ecf6287611f",
                "qop": "auth",
                "stale": "FALSE",
                "algorithm": "MD5",
            },
            {
                # Response
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
        ),
    ],
)
def test_digest(user, passwd, method, url, req, repl):
    auth = DigestClientAuth(username=user, password=passwd)

    resp = RTSPResponse()

    auth_header = ", ".join(f'{k}="{v}"' for k, v in req.items())
    data, done = resp.feed(
        """RTSP/1.0 401 Unauthorized\r\nCSeq: 0\r\nWWW-Authenticate: Digest {}\r\n\r\n""".format(
            auth_header
        ).encode()
    )

    assert not data
    assert done

    assert resp.status == 401

    retry = auth.handle_401(resp.headers)
    assert retry is True

    # Force the case where auth is to be redone
    auth.handle_ok(resp.headers)
    retry = auth.handle_401(resp.headers)
    assert retry is True

    auth_args = auth._prepare_digest_header(method=method, url=url)

    assert auth_args == repl

    # Force the case where auth is to be redone
    auth.handle_ok({"authentication-info": 'qop="auth", nextnonce="deadb00b"'})
    assert auth.info["nonce"] == "deadb00b"


@pytest.mark.parametrize(
    "user, passwd, method, url, req, repl",
    [
        # Against Axis
        (
            "root",
            "admin123",
            "DESCRIBE",
            "rtsp://cam/axis-media/media.amp",
            {
                # Challenge
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
            },
            "Basic cm9vdDphZG1pbjEyMw==",
        ),
    ],
)
def test_basic(user, passwd, method, url, req, repl):
    auth = BasicClientAuth(username=user, password=passwd)

    resp = RTSPResponse()

    auth_header = ", ".join(f'{k}="{v}"' for k, v in req.items())
    data, done = resp.feed(
        """RTSP/1.0 401 Unauthorized\r\nCSeq: 0\r\nWWW-Authenticate: Basic {}\r\n\r\n""".format(
            auth_header
        ).encode()
    )

    assert not data
    assert done

    assert resp.status == 401

    retry = auth.handle_401(resp.headers)
    assert retry is True

    # Force the case where auth is to be redone
    auth.handle_ok(resp.headers)
    retry = auth.handle_401(resp.headers)
    assert retry is True

    headers = {}
    auth.make_auth(method, url, headers)

    assert "Authorization" in headers
    assert headers["Authorization"] == repl


@pytest.mark.parametrize(
    "creds, method, params, protos, expected",
    [
        (
            # No auth: it should be fine, whatever
            {},
            "DESCRIBE",
            {
                "username": "root",
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
                "uri": "rtsp://cam/axis-media/media.amp",
                "response": "7daaf0f4e40fdff42cff28260f37914d",
            },
            ["basic", "digest"],
            True,
        ),
        (
            # No proto == no auth
            {"root": "admin123"},
            "DESCRIBE",
            {
                "username": "root",
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
                "uri": "rtsp://cam/axis-media/media.amp",
                "response": "7daaf0f4e40fdff42cff28260f37914d",
            },
            [],
            True,
        ),
        (
            {"root": "admin123"},
            "DESCRIBE",
            {
                "username": "root",
                "realm": "AXIS_ACCC8E000AA9",
                "nonce": "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
                "uri": "rtsp://cam/axis-media/media.amp",
                "response": "7daaf0f4e40fdff42cff28260f37914d",
            },
            ["basic", "digest"],
            True,
        ),
        (
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            True,
        ),
        (
            # Wrong password
            {"test": "test124"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # Wrong method
            {"test": "test123"},
            "SETUP",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # Wrong URL
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorderz:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # Wrong response
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "hello world",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # unknown user
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "helloyou",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # Missing URI
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic", "digest"],
            False,
        ),
        (
            # Digest is not supported
            {"test": "test123"},
            "DESCRIBE",
            {
                "username": "test",
                "realm": "media@genetec.com",
                "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
                "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
                "response": "85ab8f66f2930845b1ed05742a2ad8b4",
            },
            ["basic"],
            False,
        ),
        (
            # Basic!
            {"root": "admin123"},
            "DESCRIBE",
            "Basic cm9vdDphZG1pbjEyMw==",
            ["basic", "digest"],
            True,
        ),
        (
            # Basic not supported
            {"root": "admin123"},
            "DESCRIBE",
            "Basic cm9vdDphZG1pbjEyMw==",
            ["digest"],
            False,
        ),
        (
            # Basic, wrong password
            {"root": "root"},
            "DESCRIBE",
            "Basic cm9vdDphZG1pbjEyMw==",
            ["basic", "digest"],
            False,
        ),
        (
            # Basic, wrong user
            {"test": "admin123"},
            "DESCRIBE",
            "Basic cm9vdDphZG1pbjEyMw==",
            ["basic", "digest"],
            False,
        ),
    ],
)
def test_digest_auth(creds, method, params, protos, expected):
    server = ServerAuth(credentials=creds, protocols=protos)
    default_uri = "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live"

    if isinstance(params, dict):
        server.nonce = params["nonce"]
        server.realm = params["realm"]
        header = "Digest " + ",".join([f'{k}="{v}"' for k, v in params.items()])
        uri = params.get("uri", default_uri)
    else:
        uri = default_uri
        header = params

    request = RTSPRequest()
    data, done = request.feed(
        (
            f"{method} {uri} RTSP/1.0\r\n"
            "CSeq: 0\r\n"
            f"Authorization: {header}\r\n\r\n"
        ).encode()
    )
    assert done
    assert not data

    client = Mock()
    assert server.handle_auth(client, request) is expected

    if expected:
        assert not client.send_response.called
    else:
        assert client.send_response.called_with(code=401)


def test_max_reuse():
    PARAMS = {
        "username": "test",
        "realm": "media@genetec.com",
        "nonce": "900fa9ee25fb4d5e919fa17c2cd032f7",
        "uri": "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
        "response": "85ab8f66f2930845b1ed05742a2ad8b4",
    }

    header = "Digest " + ",".join([f'{k}="{v}"' for k, v in PARAMS.items()])

    # Build an auth server with max reuse == 2
    server = ServerAuth({"test": "test123"}, max_reuse=2)
    server.nonce = PARAMS["nonce"]
    server.realm = PARAMS["realm"]

    # It should work once...
    assert server.digest_auth(header, "DESCRIBE") is True
    assert server.used == 1

    # It should work twice...
    assert server.digest_auth(header, "DESCRIBE") is True
    assert server.used == 2

    # But not anymore!
    assert server.digest_auth(header, "DESCRIBE") is False

    # The effect should be that the nonce is changed and used count back to zero
    assert server.nonce and server.nonce != PARAMS["nonce"]
    assert server.used == 0

    # If we try again, we will be rejected because now nonce is different
    assert server.digest_auth(header, "DESCRIBE") is False

    # And just to be sure, let's reset nonce again and it should work again
    server.nonce = PARAMS["nonce"]
    assert server.digest_auth(header, "DESCRIBE") is True
