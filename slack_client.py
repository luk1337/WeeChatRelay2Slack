import asyncio
import time
from threading import current_thread

import slack

import config
from utils import Utils


class SlackClient:
    bot_client: slack.WebClient
    user_client: slack.WebClient
    rtm_client: slack.RTMClient

    last_dm_channels: list

    message_callback: callable

    def __init__(self):
        self.bot_client = slack.WebClient(token=config.SLACK['bot_token'], loop=asyncio.new_event_loop())
        self.user_client = slack.WebClient(token=config.SLACK['api_token'], loop=asyncio.new_event_loop())
        self.rtm_client = slack.RTMClient(token=config.SLACK['bot_token'], loop=asyncio.new_event_loop())

        self.rtm_client.on(event='message', callback=self.on_message)

        self.sync_channels()

        self.last_dm_channels = []

    def sync_channels(self):
        weechat_channels = [channel for _, channel in config.GLOBAL['channels'].items()]

        # Clean-up no longer needed non-dm channels
        self.clean_up_channels()

        # Create channels, if needed
        self.create_channels(weechat_channels)

        # Invite bot to all channels
        self.join_all_channels()

    def create_channels(self, channels: list):
        slack_channels = self.user_client.channels_list()['channels']

        channel_created = False

        for channel in channels:
            for slack_channel in slack_channels:
                if slack_channel['name'].lower() == channel.lower():
                    if slack_channel['is_archived']:
                        self.user_client.channels_unarchive(channel=slack_channel['id'])
                        channel_created = True

                    break
            else:
                self.user_client.channels_create(name=channel)
                channel_created = True

        if channel_created:
            self.join_all_channels()

    def create_dm_channels(self, channels: list):
        self.create_channels(channels)
        self.clean_up_dm_channels(channels)

        self.last_dm_channels = channels

    def clean_up_channels(self):
        weechat_channels = [channel for _, channel in config.GLOBAL['channels'].items()]
        slack_channels = self.user_client.channels_list()['channels']

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

                self.user_client.channels_archive(channel=channel['id'])

    def clean_up_dm_channels(self, channels: list):
        slack_channels = self.user_client.channels_list()['channels']

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

                self.user_client.channels_archive(channel=channel['id'])

    def join_all_channels(self):
        bot_user_id = self.bot_client.auth_test()['user_id']
        slack_channels = self.user_client.channels_list()['channels']

        # Invite bot to all channels
        for channel in slack_channels:
            if channel['is_general']:
                continue

            if channel['is_archived']:
                continue

            if bot_user_id in channel['members']:
                continue

            self.user_client.channels_invite(channel=channel['id'], user=bot_user_id)

    def send_message(self, channel: str, username: str, msg: str):
        self.bot_client.chat_postMessage(channel=channel, username=username, text=msg)

    def send_me_message(self, channel: str, msg: str):
        self.bot_client.chat_postMessage(channel=channel, username='* notice *', text=msg)

    def get_channel_by_id(self, channel_id: str):
        for channel in self.user_client.channels_list()['channels']:
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

            channel, text = self.get_channel_by_id(data['channel'])['name'], data['text']

            if is_me_message:
                self.message_callback(channel, '/me ' + text)
            else:
                self.message_callback(channel, text)

            # A silly workaround to hide forwarded messages and let them reappear once they hit relay
            self.user_client.chat_delete(channel=data['channel'], ts=data['ts'])

    def set_message_callback(self, callback: callable):
        self.message_callback = callback

    def kill_me(self):
        while current_thread().is_alive:
            time.sleep(0.15)
            pass

        # RIP
        self.future.cancel()

    def run(self):
        # Close your eyes, pretend that you don't see this code
        self.future = asyncio.ensure_future(self.rtm_client._connect_and_read(), loop=self.rtm_client._event_loop)
        try:
            self.rtm_client._event_loop.run_until_complete(self.future)
        except asyncio.CancelledError:
            pass
