import asyncio
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
        self.rtm_client = slack.RTMClient(token=Config.Slack.BotToken)
        self.rtm_client.on(event='message', callback=self.on_message)

        self.sync_channels()

        self.last_dm_channels = []

    def sync_channels(self):
        weechat_channels = [channel for _, channel in Config.Global.Channels.items()]

        # Clean-up no longer needed non-dm channels
        self.clean_up_channels()

        # Create channels, if needed
        self.create_channels(weechat_channels)

        # Invite bot to all channels
        self.join_all_channels()

    def api_get(self, method: str, token: str, **kwargs):
        return json.loads(requests.get('https://slack.com/api/{}'.format(method), data=kwargs,
                                       headers={'Authorization': 'Bearer {}'.format(token)}).content)

    def api_post(self, method: str, token: str, **kwargs):
        return json.loads(requests.post('https://slack.com/api/{}'.format(method), data=kwargs,
                                        headers={'Authorization': 'Bearer {}'.format(token)}).content)

    def create_channels(self, channels: list):
        slack_channels = self.api_get('channels.list', Config.Slack.BotToken)['channels']

        channel_created = False

        for channel in channels:
            for slack_channel in slack_channels:
                if slack_channel['name'].lower() == channel.lower():
                    if slack_channel['is_archived']:
                        self.api_post('channels.unarchive', Config.Slack.ApiToken, channel=slack_channel['id'])
                        channel_created = True

                    break
            else:
                self.api_post('channels.create', Config.Slack.ApiToken, name=channel)
                channel_created = True

        if channel_created:
            self.join_all_channels()

    def create_dm_channels(self, channels: list):
        self.create_channels(channels)
        self.clean_up_dm_channels(channels)

        self.last_dm_channels = channels

    def clean_up_channels(self):
        weechat_channels = [channel for _, channel in Config.Global.Channels.items()]
        slack_channels = self.api_get('channels.list', Config.Slack.ApiToken)['channels']

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel['name'] not in weechat_channels:
                # we can't archive general channels
                if channel['is_general']:
                    continue

                if channel['is_archived']:
                    continue

                if Utils.get_relay_direct_message_channel_for_buffer(channel['name']) is not None:
                    continue

                self.api_post('channels.archive', Config.Slack.ApiToken, channel=channel['id'])

    def clean_up_dm_channels(self, channels: list):
        slack_channels = self.api_get('channels.list', Config.Slack.ApiToken)['channels']

        # Archive all no longer necessary channels
        for channel in slack_channels:
            if channel['name'] not in channels:
                # we can't archive general channels
                if channel['is_general']:
                    continue

                if channel['is_archived']:
                    continue

                if Utils.get_relay_direct_message_channel_for_buffer(channel['name']) is None:
                    continue

                self.api_post('channels.archive', Config.Slack.ApiToken, channel=channel['id'])

    def join_all_channels(self):
        bot_user_id = self.api_post('auth.test', Config.Slack.BotToken)['user_id']
        slack_channels = self.api_get('channels.list', Config.Slack.ApiToken)['channels']

        # Invite bot to all channels
        for channel in slack_channels:
            if channel['is_general']:
                continue

            if channel['is_archived']:
                continue

            if bot_user_id in channel['members']:
                continue

            self.api_post('channels.invite', Config.Slack.ApiToken, channel=channel['id'], user=bot_user_id)

    def send_message(self, channel: str, username: str, msg: str):
        self.api_post('chat.postMessage', Config.Slack.BotToken, channel=channel, username=username, text=msg)

    def send_me_message(self, channel: str, msg: str):
        self.api_post('chat.postMessage', Config.Slack.BotToken, channel=channel, username='* notice *', text=msg)

    def get_channel_by_id(self, channel_id: str):
        slack_channels = self.api_get('channels.list', Config.Slack.ApiToken)['channels']

        for channel in slack_channels:
            if channel['id'] == channel_id:
                return channel

        return None

    def get_private_file(self, url: str):
        return requests.get(url, headers={'Authorization': 'Bearer {}'.format(Config.Slack.BotToken)}).content

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

            channel, text = self.get_channel_by_id(data['channel'])['name'], data['text']

            if is_me_message:
                self.message_callback(channel, '/me ' + text)
            else:
                self.message_callback(channel, text)

            if Config.GcfUpload.URL and Config.GcfUpload.ApiKey and 'files' in data:
                for file in data['files']:
                    url = Utils.upload_to_gcf_upload(self.get_private_file(file['url_private']))
                    self.message_callback(channel, url)

            # A silly workaround to hide forwarded messages and let them reappear once they hit relay
            self.api_post('chat.delete', Config.Slack.ApiToken, channel=data['channel'], ts=data['ts'])

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
