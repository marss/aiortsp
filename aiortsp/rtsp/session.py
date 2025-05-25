"""
RTSP Media Session setup and control
"""
import asyncio
import calendar
import json
import logging
import math
import re
from datetime import datetime
from typing import Set
from urllib.parse import urlparse

from aiortsp.rtcp.stats import RTCPStats
from aiortsp.transport import RTPTransport
from .errors import RTSPError
from .parser import RTSPResponse
from .sdp import SDP

default_logger = logging.getLogger(__name__)


def sanitize_rtsp_url(url: str) -> str:
    """
    Sanitize an RTSP url, removing exotic scheme and authentication.
    """
    p_url = urlparse(url)
    scheme = p_url.scheme
    if scheme != 'rtsp' and scheme != 'rtsps':
        scheme = 'rtsp'
    return p_url._replace(
        scheme=scheme,
        netloc=f'{p_url.hostname}' if p_url.port is None else f'{p_url.hostname}:{p_url.port}'
    ).geturl()


class RTSPMediaSession:
    """
    RTSP Media Session
    """

    def __init__(self, connection, media_url, transport_template: RTPTransport, media_type='video',
                 use_all_available_streams=False, logger=None):
        self.connection = connection
        self.media_url = sanitize_rtsp_url(media_url)
        self.transport_template = transport_template  # Store the template
        self.transports = {}  # Initialize as a dictionary
        self.logger = logger or default_logger
        self.use_all_available_streams = use_all_available_streams

        if isinstance(media_type, str):
            self.media_types = [media_type]
        else:
            self.media_types = media_type

        self.is_setup = False
        self.sdp = None
        self.server_rtp = None
        self.server_rtcp = None

        self.session_id = None
        self.session_keepalive = 60
        self.session_options: Set[str] = set()

    async def __aenter__(self):
        """
        At entrance of env, we expect the stream to be ready for playback
        """
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val and exc_type != asyncio.CancelledError:
            self.logger.error('exception during session: %s %s', exc_type, exc_val)
        await self.teardown()

    async def setup(self):
        """
        Perform SETUP for selected media streams.
        """
        # Get supported options
        resp = await self._send('OPTIONS', url=self.media_url)
        self.save_options(resp)

        # Get SDP
        resp = await self._send('DESCRIBE', headers={'Accept': 'application/sdp'})

        if 'content-base' in resp.headers:
            self.media_url = resp.headers['content-base']
            self.logger.info('using base url: %s', self.media_url)

        self.logger.debug('received SDP:\n%s', resp.content)
        self.sdp = SDP(resp.content)
        self.logger.debug('parsed SDP:\n%s', json.dumps(self.sdp, indent=2))

        media_to_setup = []
        if self.use_all_available_streams:
            media_to_setup = self.sdp.get('medias', [])
        else:
            for idx, media_type in enumerate(self.media_types):
                media_desc = self.sdp.get_media(media_type=media_type, media_idx=0) # Assuming one of each type for now
                if media_desc:
                    media_to_setup.append(media_desc)
                else:
                    self.logger.warning(f"Could not find media description for type: {media_type}")

        if not media_to_setup:
            self.logger.error("No media streams found or selected for setup.")
            return

        setup_count = 0
        for media_description in media_to_setup:
            media_type = media_description['type']
            # media_idx might be needed if multiple streams of the same type exist and are uniquely identified by index
            # For now, using the media_description's own index if available, or default to 0
            media_idx = media_description.get('idx', 0) # This 'idx' might not be standard in SDP media object

            # Correctly determine setup_url. The `setup_url` method in SDP class might need to handle this.
            # Assuming `media_description` contains enough info or `setup_url` can find it.
            # The `control` attribute from SDP media description is often the relative path.
            control_attribute = media_description.get('control')
            if not control_attribute:
                self.logger.warning(f"No control attribute found for media type {media_type}, skipping setup.")
                continue

            if control_attribute.startswith('rtsp://') or control_attribute.startswith('rtsps://'):
                setup_url = control_attribute
            elif self.media_url.endswith('/') and control_attribute.startswith('/'): # Avoid double slashes
                setup_url = self.media_url[:-1] + control_attribute
            elif not self.media_url.endswith('/') and not control_attribute.startswith('/'):
                 setup_url = self.media_url + '/' + control_attribute
            else:
                setup_url = self.media_url + control_attribute


            self.logger.info(f'Setting up {media_type} using URL: {setup_url}')

            # Instantiate a new RTPTransport for this stream
            # Assuming transport_template is the class of the transport or a factory
            new_transport = type(self.transport_template)() # Create new instance

            headers = {}
            new_transport.on_transport_request(headers)
            try:
                resp = await self.connection.send_request('SETUP', url=setup_url, headers=headers)
                new_transport.on_transport_response(resp.headers)
                self.logger.info(f'{media_type} stream correctly setup: {resp}')

                self.transports[media_type] = new_transport
                self.save_session(resp)  # Assume single session ID, updated by the latest SETUP
                await new_transport.warmup()
                setup_count += 1
            except RTSPError as e:
                self.logger.error(f"Failed to setup {media_type} stream: {e}")
            except Exception as e: # pylint: disable=broad-except
                self.logger.error(f"An unexpected error occurred during {media_type} setup: {e}")


        if setup_count > 0:
            self.is_setup = True
        else:
            self.logger.error("Failed to set up any media stream.")


    @property
    def stats(self) -> dict: # Changed to dict
        """Stats convenient accessor"""
        return {media_type: transport.stats for media_type, transport in self.transports.items()}

    def save_options(self, resp: RTSPResponse):
        """
        Extract method lists from OPTIONS response
        """
        # Extract session Id
        if 'public' not in resp.headers:
            raise RTSPError('error on OPTIONS: `Public` not found')

        self.session_options = {o.strip().upper() for o in resp.headers['public'].split(',')}
        self.logger.info('session options: %s', self.session_options)

    def save_session(self, resp: RTSPResponse):
        """
        Extract session ID and timeout
        """
        # Extract session Id
        if 'session' not in resp.headers:
            raise RTSPError('error on SETUP: session not found')

        # Get session id
        session_params = resp.headers['session'].split(';')
        self.session_id = session_params[0].strip()
        timeout = 60
        if len(session_params) > 1:
            for option in session_params[1:]:
                option = option.strip()
                if not option.startswith('timeout'):
                    continue

                _, timeout_ = option.split('=', 1)
                timeout = int(timeout_)

        self.session_keepalive = int(timeout * 0.9)
        self.logger.info(
            'session id: %s, timeout: %s, keep_alive: %s',
            self.session_id, timeout, self.session_keepalive
        )

    async def teardown(self):
        """
        Perform TEARDOWN
        """
        if self.connection.running and self.transports: # Check if there's anything to tear down
            self.logger.info('stopping session/playback...')
            # Assuming a single TEARDOWN for the whole session
            resp = await self._send('TEARDOWN')
            self.logger.debug('response to teardown: %s', resp)

            for transport in self.transports.values():
                if hasattr(transport, 'close') and asyncio.iscoroutinefunction(transport.close):
                    await transport.close()
                elif hasattr(transport, 'close'):
                    transport.close()
            self.transports.clear()
            self.is_setup = False
            return resp

        self.logger.info('session closed or no transports to teardown.')
        # Ensure transports are cleared even if connection wasn't running
        for transport in self.transports.values():
            if hasattr(transport, 'close') and asyncio.iscoroutinefunction(transport.close):
                await transport.close()
            elif hasattr(transport, 'close'):
                transport.close()
        self.transports.clear()
        self.is_setup = False


    async def _send(self, method, url=None, headers=None):
        if headers is None:
            headers = {}
        if self.session_id:
            headers['Session'] = self.session_id
        return await self.connection.send_request(method, url or self.media_url, headers)

    @staticmethod
    def ts_to_clock(seek: float) -> str:
        """
        Must return a string in the following format:
            20190322T043720.003Z
        :param seek: utc timestamp
        """
        res = datetime.utcfromtimestamp(seek).strftime('%Y%m%dT%H%M%S')
        rem = seek - math.floor(seek)
        if rem:
            res += str(round(rem, 3))[1:]
        res += 'Z'
        return res

    @staticmethod
    def response_to_ts(resp, default_ts):
        """
        Try to return real play time, or default if not found
        """
        try:
            res = re.match(r'^ *clock *= *(?P<date>\d{8})T(?P<time>\d{6})(\.(?P<milli>\d+))?Z *-', resp.headers.get('range'))

            if not res:
                return default_ts

            content = res.groupdict()
            dt = datetime.strptime(content['date'] + content['time'], '%Y%m%d%H%M%S')

            ts = calendar.timegm(dt.timetuple())

            if content["milli"]:
                ts += float(f'0.{content["milli"]}')

            return ts
        except Exception:  # pylint: disable=broad-except
            # @TODO Should we log anything?
            return default_ts

    async def play(self, seek=None, speed=1):
        """
        Send a PLAY request
        :param seek: UTC timestamp where to ask to start. By default, uses 'now'.
        :param speed: Replay speed. Could be used for fast forward playing.
        """
        if seek:
            start = self.ts_to_clock(seek)
            range_ = f'clock={start}-'
        else:
            start = 'now'
            range_ = 'npt=now-'

        self.logger.info(
            'start playing %s at time `%s` and speed `%s`...',
            self.media_url, start, speed
        )

        resp = await self._send('PLAY', headers={
            'Scale': speed,
            'Range': range_
        })
        self.logger.debug('response to play: %s', resp)
        return resp

    async def pause(self):
        """
        Send a PAUSE, temporarily stopping RTP flow but keeping session alive.
        """
        self.logger.debug('sending keep alive')
        resp = await self._send('PAUSE')
        self.logger.debug('response to pause: %s', resp)
        return resp

    async def keep_alive(self):
        """
        Send a GET_PARAMETER or OPTIONS message in order to keep session alive.
        """
        self.logger.debug('sending keep alive')

        # We must send a supported command
        if 'GET_PARAMETER' in self.session_options:
            resp = await self._send('GET_PARAMETER')
        elif 'OPTIONS' in self.session_options:
            resp = await self._send('OPTIONS')
        else:
            self.logger.info('Does not support GET_PARAMETER or OPTIONS: not sending keep alive.')
            resp = None

        self.logger.debug('response to keep_alive: %s', resp)
        return resp
