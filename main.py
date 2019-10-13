#!/usr/bin/env python3
import logging
import threading

from config import Config
from relay_client import RelayClient
from slack_client import SlackClient
from utils import Utils


class WeeChatRelay2Slack:
    relay_client: RelayClient
    slack_client: SlackClient

    def __init__(self):
        self.relay_client = RelayClient()
        self.relay_client.set_on_buffer_line_added_callback(self._on_buffer_line_added)
        self.relay_client.set_on_buffer_opened_callback_callback(self._on_buffer_opened)
        self.relay_client.set_on_buffer_closing_callback_callback(self._on_buffer_closing)

        self.slack_client = SlackClient()
        self.slack_client.set_message_callback(self._on_slack_message)
        self.slack_client.create_dm_channels([buffer for _, buffer in self.relay_client.get_direct_message_buffers()])

    def _on_buffer_line_added(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_line_added, args=(response, True)).start()
            return

        is_generic_server_msg = bool({'irc_401',
                                      'irc_402',
                                      'irc_join',
                                      'irc_kick',
                                      'irc_mode',
                                      'irc_nick',
                                      'irc_part',
                                      'irc_topic',
                                      'irc_quit'} & set(response.get('tags_array', [])))
        is_privmsg = 'irc_privmsg' in response.get('tags_array', [])

        if not any((is_generic_server_msg, is_privmsg)):
            return

        if response.get('buffer', '').startswith('gui_'):
            buffer = self.relay_client.wait_for_buffer_by_pointer(response.get('buffer', ''))
        else:
            buffer = self.relay_client.wait_for_buffer_by_pointer(f'0x{response.get("buffer", "")}')

        if buffer is None:
            logging.error(f'Timed out while waiting for buffer {response.get("buffer", "")}')
            return

        buffer_name, msg = buffer.full_name, Utils.weechat_string_remove_color(response.get('message', ''))

        if buffer_name not in Config.Global.Channels:
            buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

            if buffer_name is not None:
                # Wait for slack channel
                while buffer_name not in self.slack_client.last_dm_channels:
                    pass
        else:
            buffer_name = Config.Global.Channels[buffer_name]

        if buffer_name is not None:
            if is_generic_server_msg:
                self.slack_client.send_me_message(
                    buffer_name, Utils.weechat_string_remove_color(response.get('message', '')))
            elif is_privmsg:
                prefix = Utils.weechat_string_remove_color(response.get('prefix', ''))

                if 'irc_action' in response.get('tags_array', []):
                    self.slack_client.send_me_message(buffer_name, msg)
                else:
                    self.slack_client.send_message(buffer_name, prefix, msg)

    def _on_buffer_opened(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_opened, args=(response, True)).start()
            return

        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response.get('full_name', ''))

        if buffer_name is not None and buffer_name not in self.slack_client.last_dm_channels:
            logging.info(f'Adding DM channel: {buffer_name}')

            self.slack_client.create_dm_channels(self.slack_client.last_dm_channels + [buffer_name])

    def _on_buffer_closing(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_closing, args=(response, True)).start()
            return

        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response.get('full_name', ''))

        if buffer_name is not None and buffer_name in self.slack_client.last_dm_channels:
            logging.info(f'Closing DM channel: {buffer_name}')

            self.slack_client.create_dm_channels([c for c in self.slack_client.last_dm_channels if c != buffer_name])

    def _on_slack_message(self, channel: str, msg: str):
        weechat_channel = Utils.get_relay_direct_message_channel_for_buffer(channel)

        if weechat_channel is not None:
            self.relay_client.input(weechat_channel, msg)
        else:
            for weechat_channel, slack_channel in Config.Global.Channels.items():
                if slack_channel == channel:
                    self.relay_client.input(weechat_channel, msg)
                    break

    def run(self):
        threads = [
            *self.relay_client.tasks(),
            *self.slack_client.tasks(),
        ]

        [thread.start() for thread in threads]

        try:
            [thread.join() for thread in threads]
        except KeyboardInterrupt:
            logging.info('Bye!')

            # Kill existing threads
            for thread in threads:
                thread.is_alive = False
                thread.join()


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

    # Run WeeChatRelay2Slack
    WeeChatRelay2Slack().run()
