import asyncio
import html
import json
import logging
import threading
import time
from threading import current_thread

import requests
import slack

from config import Config
from file_upload import FileUpload


class SlackClient:
    rtm_client: slack.RTMClient

    last_dm_channels: list

    message_callback: callable

    def __init__(self):
        self._check_auth()
        self._sync_channels()

        self.rtm_client = slack.RTMClient(token=Config.Slack.Token)
        self.rtm_client.on(event='message', callback=self._on_message)

        self.last_dm_channels = []

    def _api_get(self, method: str, **kwargs):
        return json.loads(requests.get(f'https://slack.com/api/{method}', data=kwargs,
                                       headers={'Authorization': f'Bearer {Config.Slack.Token}'}).content)

    def _api_post(self, method: str, **kwargs):
        return json.loads(requests.post(f'https://slack.com/api/{method}', data=kwargs,
                                        headers={'Authorization': f'Bearer {Config.Slack.Token}'}).content)

    def _raw_get(self, url: str):
        return requests.get(url, headers={'Authorization': f'Bearer {Config.Slack.Token}'}).content

    def _check_auth(self):
        response = self._api_get('auth.test')

        if not response.get('ok'):
            raise Exception('Invalid Slack token!')

    def _sync_channels(self):
        # Clean-up no longer needed non-dm channels
        self._clean_up_channels()

        # Create channels, if needed
        self.create_channels([channel for _, channel in Config.Global.Channels.items()])

    def _clean_up_channels(self):
        weechat_channels = [channel for _, channel in Config.Global.Channels.items()]
        slack_channels = self._api_get('channels.list').get('channels', [])

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel.get('name') not in weechat_channels:
                if channel.get('is_general') or channel.get('is_archived'):
                    continue

                self._api_post('channels.archive', channel=channel.get('id'))

    def _clean_up_dm_channels(self, channels: list, s2w_dm_channels_map: dict):
        slack_channels = self._api_get('channels.list').get('channels', [])

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel.get('name') not in channels:
                if channel.get('is_general') or channel.get('is_archived'):
                    continue

                if channel.get('name') not in s2w_dm_channels_map:
                    continue

                self._api_post('channels.archive', channel=channel.get('id'))

    def create_channels(self, channels: list):
        slack_channels = self._api_get('channels.list').get('channels', [])

        for channel in channels:
            for slack_channel in slack_channels:
                if slack_channel.get('name').lower() == channel.lower():
                    if slack_channel.get('is_archived'):
                        self._api_post('channels.unarchive', channel=slack_channel.get('id'))

                    break
            else:
                self._api_post('channels.create', name=channel)

    def create_dm_channels(self, channels: list, s2w_dm_channels_map: dict):
        self.create_channels(channels)
        self._clean_up_dm_channels(channels, s2w_dm_channels_map)

        self.last_dm_channels = channels

    def wait_for_dm_channel(self, channel: str, timeout: int = 5):
        start = time.time()

        while time.time() < start + timeout:
            if channel in self.last_dm_channels:
                return

            time.sleep(0.15)

        logging.info('Timed out while waiting for DM channel, attempting to create one manually')
        self.create_dm_channels(self.last_dm_channels + [channel])

    def send_message(self, channel: str, username: str, msg: str):
        self._api_post('chat.postMessage', channel=channel, username=username, text=msg)

    def send_me_message(self, channel: str, msg: str):
        self._api_post('chat.postMessage', channel=channel, username='* notice *', text=msg)

    def _get_channel_by_id(self, channel_id: str):
        slack_channels = self._api_get('channels.list').get('channels', [])

        for channel in slack_channels:
            if channel.get('id') == channel_id:
                return channel

        return None

    def _on_message(self, **payload):
        if self.message_callback is not None:
            data = payload.get('data')

            # We don't want to forward any bot messages
            if 'user' not in data:
                return

            has_subtype = 'subtype' in data
            is_me_message = data.get('subtype') == 'me_message'

            # Suppress all 'subtype' messages but me_message
            if has_subtype and not is_me_message:
                return

            # We don't want to forward slackbot messages
            if data.get('user') == 'USLACKBOT':
                return

            channel, text = self._get_channel_by_id(data.get('channel')).get('name'), html.unescape(data.get('text'))

            if is_me_message:
                self.message_callback(channel, f'/me {text}')
            else:
                self.message_callback(channel, text)

            if 'files' in data:
                for file in data.get('files', []):
                    status, msg = FileUpload.upload(file.get('name'), self._raw_get(file.get('url_private')),
                                                    file.get('mimetype'))

                    if status:
                        self.message_callback(channel, msg)
                    else:
                        self.send_message(data.get('channel'), '* weerelay2slack *', msg)

            # A silly workaround to hide forwarded messages and let them reappear once they hit relay
            self._api_post('chat.delete', channel=data.get('channel'), ts=data.get('ts'))

    def set_message_callback(self, callback: callable):
        self.message_callback = callback

    def _kill_me(self):
        while current_thread().is_alive:
            time.sleep(0.15)

        # RIP
        self.future.cancel()

    def _run(self):
        # Close your eyes, pretend that you don't see this code
        self.future = asyncio.ensure_future(self.rtm_client._connect_and_read(), loop=self.rtm_client._event_loop)
        try:
            self.rtm_client._event_loop.run_until_complete(self.future)
        except asyncio.CancelledError:
            pass

    def tasks(self):
        return [
            threading.Thread(target=self._kill_me),
            threading.Thread(target=self._run),
        ]
