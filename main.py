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

    # Slack <> WeeChat channel map
    s2w_dm_channels_map = {}

    def __init__(self):
        self.relay_client = RelayClient()
        self.relay_client.set_on_buffer_line_added_callback(self._on_buffer_line_added)
        self.relay_client.set_on_buffer_opened_callback(self._on_buffer_opened)
        self.relay_client.set_on_buffer_closing_callback(self._on_buffer_closing)
        self.relay_client.set_on_post_setup_buffers_callback(self._on_post_setup_buffers)
        self.relay_client.init()

        self.slack_client = SlackClient()
        self.slack_client.set_message_callback(self._on_slack_message)
        self.slack_client.create_dm_channels([buffer for _, buffer in self.relay_client.get_direct_message_buffers()],
                                             self.s2w_dm_channels_map)

    def _on_buffer_line_added(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_line_added, args=(response, True)).start()
            return

        buffer_pointer = response.get('buffer', '')
        message = response.get('message', '')
        tags_array = response.get('tags_array', [])

        is_generic_server_msg = bool({'irc_401',
                                      'irc_402',
                                      'irc_join',
                                      'irc_kick',
                                      'irc_mode',
                                      'irc_nick',
                                      'irc_nick_back',
                                      'irc_part',
                                      'irc_topic',
                                      'irc_quit'} & set(tags_array))
        is_privmsg = 'irc_privmsg' in tags_array

        if not any((is_generic_server_msg, is_privmsg)):
            return

        if buffer_pointer.startswith('gui_'):
            buffer = self.relay_client.wait_for_buffer_by_pointer(buffer_pointer)
        else:
            buffer = self.relay_client.wait_for_buffer_by_pointer(f'0x{buffer_pointer}')

        if buffer is None:
            logging.error(f'Timed out while waiting for buffer {buffer_pointer}')
            return

        if buffer.full_name in Config.Relay.Filters:
            for filter_tags in Config.Relay.Filters[buffer.full_name]:
                if all(x in tags_array for x in filter_tags.split('+')):
                    return

        buffer_name, msg = buffer.full_name, Utils.weechat_string_remove_color(message)

        if buffer_name not in Config.Global.Channels:
            buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

            if buffer_name is not None:
                self.slack_client.wait_for_dm_channel(buffer_name)
        else:
            buffer_name = Config.Global.Channels[buffer_name]

        if buffer_name is not None:
            if is_generic_server_msg:
                self.slack_client.send_me_message(buffer_name, msg)
            elif is_privmsg:
                if 'irc_action' in tags_array:
                    self.slack_client.send_me_message(buffer_name, msg)
                else:
                    prefix = Utils.weechat_string_remove_color(response.get('prefix', ''))
                    self.slack_client.send_message(buffer_name, prefix, msg)

    def _on_buffer_opened(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_opened, args=(response, True)).start()
            return

        full_name = response.get('full_name', '')
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(full_name)

        if buffer_name is None:
            return

        if buffer_name not in self.slack_client.last_dm_channels:
            logging.info(f'Adding DM channel: {buffer_name}')

            self.slack_client.create_dm_channels(self.slack_client.last_dm_channels + [buffer_name],
                                                 self.s2w_dm_channels_map)

        self.s2w_dm_channels_map[buffer_name] = full_name

    def _on_buffer_closing(self, response: dict, run_async: bool = False):
        if not run_async:
            threading.Thread(target=self._on_buffer_closing, args=(response, True)).start()
            return

        full_name = response.get('full_name', '')
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(full_name)

        if buffer_name is None:
            return

        if buffer_name in self.slack_client.last_dm_channels:
            logging.info(f'Closing DM channel: {buffer_name}')

            self.slack_client.create_dm_channels([c for c in self.slack_client.last_dm_channels if c != buffer_name],
                                                 self.s2w_dm_channels_map)

        if buffer_name in self.s2w_dm_channels_map:
            del self.s2w_dm_channels_map[buffer_name]

    def _on_slack_message(self, channel: str, msg: str):
        weechat_channel = self.s2w_dm_channels_map[channel] if channel in self.s2w_dm_channels_map else None

        if weechat_channel is not None:
            self.relay_client.input(weechat_channel, msg)
        else:
            for weechat_channel, slack_channel in Config.Global.Channels.items():
                if slack_channel == channel:
                    self.relay_client.input(weechat_channel, msg)
                    break

    def _on_post_setup_buffers(self):
        for buffer in self.relay_client.buffers:
            buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer.full_name)

            if buffer_name is not None:
                self.s2w_dm_channels_map[buffer_name] = buffer.full_name

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
