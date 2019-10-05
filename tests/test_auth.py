import pytest

from aiortsp.rtsp.auth import DigestAuth, BasicAuth
from aiortsp.rtsp.parser import RTSPResponse


@pytest.mark.parametrize('user, passwd, method, url, req, repl', [

    ('root', 'admin123', 'DESCRIBE', 'rtsp://cam/axis-media/media.amp', {
        # Challenge
        'realm': "AXIS_ACCC8E000AA9",
        'nonce': "0024e47aY398109708de9ccd8056c58a068a59540a99d3"
    }, {
        # Response
        "username": "root",
        'realm': "AXIS_ACCC8E000AA9",
        'nonce': "0024e47aY398109708de9ccd8056c58a068a59540a99d3",
        'uri': "rtsp://cam/axis-media/media.amp",
        'response': "7daaf0f4e40fdff42cff28260f37914d",
    }),

    ('test', 'test123', 'DESCRIBE', 'rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live', {
        # Challenge
        'realm': "media@genetec.com",
        'nonce': "900fa9ee25fb4d5e919fa17c2cd032f7",
        'opque': "0bd45fa6a89e4873a4c80ecf6287611f",
        'qop': "auth",
        'stale': "FALSE",
        'algorithm': "MD5"
    }, {
        # Response
        "username": "test",
        'realm': "media@genetec.com",
        'nonce': "900fa9ee25fb4d5e919fa17c2cd032f7",
        'uri': "rtsp://recorder:654/00000001-0000-babe-0000-accc8e000aa7/live",
        'response': "85ab8f66f2930845b1ed05742a2ad8b4",
    }),
])
def test_digest(user, passwd, method, url, req, repl):
    auth = DigestAuth(username=user, password=passwd)

    resp = RTSPResponse()

    auth_header = ', '.join(f'{k}="{v}"' for k, v in req.items())
    data, done = resp.feed(
        """RTSP/1.0 401 Unauthorized\r\nCSeq: 0\r\nWWW-Authenticate: Digest {}\r\n\r\n""".format(auth_header).encode())

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
    auth.handle_ok({
        'authentication-info': 'qop="auth", nextnonce="deadb00b"'
    })
    assert auth.info['nonce'] == 'deadb00b'


@pytest.mark.parametrize('user, passwd, method, url, req, repl', [

    # Against Axis
    ('root', 'admin123', 'DESCRIBE', 'rtsp://cam/axis-media/media.amp', {
        # Challenge
        'realm': "AXIS_ACCC8E000AA9",
        'nonce': "0024e47aY398109708de9ccd8056c58a068a59540a99d3"
    }, 'Basic cm9vdDphZG1pbjEyMw=='),
])
def test_basic(user, passwd, method, url, req, repl):
    auth = BasicAuth(username=user, password=passwd)

    resp = RTSPResponse()

    auth_header = ', '.join(f'{k}="{v}"' for k, v in req.items())
    data, done = resp.feed(
        """RTSP/1.0 401 Unauthorized\r\nCSeq: 0\r\nWWW-Authenticate: Basic {}\r\n\r\n""".format(auth_header).encode())

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

    assert 'Authorization' in headers
    assert headers['Authorization'] == repl
