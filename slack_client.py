import asyncio
import html
import json
import time
from threading import current_thread

import requests
import slack

from config import Config
from utils import Utils


class SlackClient:
    rtm_client: slack.RTMClient

    last_dm_channels: list

    message_callback: callable

    def __init__(self):
        self._check_auth()

        self.rtm_client = slack.RTMClient(token=Config.Slack.Token)
        self.rtm_client.on(event='message', callback=self.on_message)

        self.sync_channels()

        self.last_dm_channels = []

    def _check_auth(self):
        response = self.api_get('auth.test')

        if not response['ok']:
            raise Exception('Invalid Slack token!')

    def sync_channels(self):
        # Clean-up no longer needed non-dm channels
        self.clean_up_channels()

        # Create channels, if needed
        self.create_channels([channel for _, channel in Config.Global.Channels.items()])

    def api_get(self, method: str, **kwargs):
        return json.loads(requests.get('https://slack.com/api/{}'.format(method), data=kwargs,
                                       headers={'Authorization': 'Bearer {}'.format(Config.Slack.Token)}).content)

    def api_post(self, method: str, **kwargs):
        return json.loads(requests.post('https://slack.com/api/{}'.format(method), data=kwargs,
                                        headers={'Authorization': 'Bearer {}'.format(Config.Slack.Token)}).content)

    def get_private_file(self, url: str):
        return requests.get(url, headers={'Authorization': 'Bearer {}'.format(Config.Slack.Token)}).content

    def create_channels(self, channels: list):
        slack_channels = self.api_get('channels.list')['channels']

        for channel in channels:
            for slack_channel in slack_channels:
                if slack_channel['name'].lower() == channel.lower():
                    if slack_channel['is_archived']:
                        self.api_post('channels.unarchive', channel=slack_channel['id'])

                    break
            else:
                self.api_post('channels.create', name=channel)

    def create_dm_channels(self, channels: list):
        self.create_channels(channels)
        self.clean_up_dm_channels(channels)

        self.last_dm_channels = channels

    def clean_up_channels(self):
        weechat_channels = [channel for _, channel in Config.Global.Channels.items()]
        slack_channels = self.api_get('channels.list')['channels']

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel['name'] not in weechat_channels:
                if channel['is_general'] or channel['is_archived']:
                    continue

                if Utils.get_relay_direct_message_channel_for_buffer(channel['name']) is not None:
                    continue

                self.api_post('channels.archive', channel=channel['id'])

    def clean_up_dm_channels(self, channels: list):
        slack_channels = self.api_get('channels.list')['channels']

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel['name'] not in channels:
                if channel['is_general'] or channel['is_archived']:
                    continue

                if Utils.get_relay_direct_message_channel_for_buffer(channel['name']) is None:
                    continue

                self.api_post('channels.archive', channel=channel['id'])

    def send_message(self, channel: str, username: str, msg: str):
        self.api_post('chat.postMessage', channel=channel, username=username, text=msg)

    def send_me_message(self, channel: str, msg: str):
        self.api_post('chat.postMessage', channel=channel, username='* notice *', text=msg)

    def get_channel_by_id(self, channel_id: str):
        slack_channels = self.api_get('channels.list')['channels']

        for channel in slack_channels:
            if channel['id'] == channel_id:
                return channel

        return None

    def on_message(self, **payload):
        if self.message_callback is not None:
            data = payload['data']

            # We don't want to forward any bot messages
            if 'user' not in data:
                return

            has_subtype = 'subtype' in data
            is_me_message = has_subtype and data['subtype'] == 'me_message'

            # Suppress all 'subtype' messages but me_message
            if has_subtype and not is_me_message:
                return

            # We don't want to forward slackbot messages
            if data['user'] == 'USLACKBOT':
                return

            channel, text = self.get_channel_by_id(data['channel'])['name'], html.unescape(data['text'])

            if is_me_message:
                self.message_callback(channel, '/me ' + text)
            else:
                self.message_callback(channel, text)

            if Config.GcfUpload.URL and Config.GcfUpload.ApiKey and 'files' in data:
                for file in data['files']:
                    url = Utils.upload_to_gcf_upload(self.get_private_file(file['url_private']))
                    self.message_callback(channel, url)

            # A silly workaround to hide forwarded messages and let them reappear once they hit relay
            self.api_post('chat.delete', channel=data['channel'], ts=data['ts'])

    def set_message_callback(self, callback: callable):
        self.message_callback = callback

    def kill_me(self):
        while current_thread().is_alive:
            time.sleep(0.15)

        # RIP
        self.future.cancel()

    def run(self):
        # Close your eyes, pretend that you don't see this code
        self.future = asyncio.ensure_future(self.rtm_client._connect_and_read(), loop=self.rtm_client._event_loop)
        try:
            self.rtm_client._event_loop.run_until_complete(self.future)
        except asyncio.CancelledError:
            pass
