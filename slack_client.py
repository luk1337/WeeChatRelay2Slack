import asyncio
import concurrent
from threading import current_thread

import slack

import config


class SlackClient:
    bot_client: slack.WebClient
    user_client: slack.WebClient
    rtm_client: slack.RTMClient

    message_callback: callable

    def __init__(self):
        self.bot_client = slack.WebClient(token=config.SLACK['bot_token'], loop=asyncio.new_event_loop())
        self.user_client = slack.WebClient(token=config.SLACK['api_token'], loop=asyncio.new_event_loop())
        self.rtm_client = slack.RTMClient(token=config.SLACK['bot_token'], loop=asyncio.new_event_loop())

        self.rtm_client.on(event='message', callback=self.on_message)

        self.sync_channels()

    def sync_channels(self):
        bot_user_id = self.bot_client.auth_test()['user_id']
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

                self.user_client.channels_archive(channel=channel['id'])

        # Create channels, if needed
        for channel in weechat_channels:
            if not any(c['name'] == channel for c in slack_channels):
                self.user_client.channels_create(name=channel)

        # Update channel list
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

    def send_message(self, channel, username, msg):
        self.bot_client.chat_postMessage(channel=channel, username=username, text=msg)

    def get_channel_by_id(self, channel_id):
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

            channel, text = self.get_channel_by_id(data['channel'])['name'], data['text']

            self.message_callback(channel, text)

            # A silly workaround to hide forwarded messages and let them reappear once they hit relay
            self.user_client.chat_delete(channel=data['channel'], ts=data['ts'])

    def set_message_callback(self, f):
        self.message_callback = f

    def kill_me(self):
        while current_thread().is_alive:
            pass

        # RIP
        self.future.cancel()

    def run(self):
        # Close your eyes, pretend that you don't see this code
        self.future = asyncio.ensure_future(self.rtm_client._connect_and_read(), loop=self.rtm_client._event_loop)
        try:
            self.rtm_client._event_loop.run_until_complete(self.future)
        except concurrent.futures._base.CancelledError:
            pass
