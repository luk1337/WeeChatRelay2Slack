#!/usr/bin/env python3
import logging
import threading

from config import Config
from relay_client import RelayClient
from slack_client import SlackClient
from utils import Utils

# globals
relay_client: RelayClient
slack_client: SlackClient


def on_buffer_line_added(response: dict, run_async: bool = False):
    global relay_client, slack_client

    if not run_async:
        threading.Thread(target=on_buffer_line_added, args=(response, True)).start()
        return

    is_generic_server_msg = bool({'irc_401',
                                  'irc_402',
                                  'irc_join',
                                  'irc_kick',
                                  'irc_mode',
                                  'irc_nick',
                                  'irc_part',
                                  'irc_topic',
                                  'irc_quit'} & set(response['tags_array']))
    is_privmsg = 'irc_privmsg' in response['tags_array']

    if not any((is_generic_server_msg, is_privmsg)):
        return

    if response['buffer'].startswith('gui_'):
        buffer = relay_client.wait_for_buffer_by_pointer(response['buffer'])
    else:
        buffer = relay_client.wait_for_buffer_by_pointer(f'0x{response["buffer"]}')

    if buffer is None:
        logging.error(f'Timed out while waiting for buffer {response["buffer"]}')
        return

    buffer_name, msg = buffer.full_name, Utils.weechat_string_remove_color(response['message'])

    if buffer_name not in Config.Global.Channels:
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

        if buffer_name is not None:
            # Wait for slack channel
            while buffer_name not in slack_client.last_dm_channels:
                pass
    else:
        buffer_name = Config.Global.Channels[buffer_name]

    if buffer_name is not None:
        if is_generic_server_msg:
            slack_client.send_me_message(buffer_name, Utils.weechat_string_remove_color(response['message']))
        elif is_privmsg:
            prefix = Utils.weechat_string_remove_color(response['prefix'])

            if 'irc_action' in response['tags_array']:
                slack_client.send_me_message(buffer_name, msg)
            else:
                slack_client.send_message(buffer_name, prefix, msg)


def on_buffer_opened(response: dict, run_async: bool = False):
    global slack_client

    if not run_async:
        threading.Thread(target=on_buffer_opened, args=(response, True)).start()
        return

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response['full_name'])

    if buffer_name is not None and buffer_name not in slack_client.last_dm_channels:
        logging.info(f'Adding DM channel: {buffer_name}')

        slack_client.create_dm_channels(slack_client.last_dm_channels + [buffer_name])


def on_buffer_closing(response: dict, run_async: bool = False):
    global slack_client

    if not run_async:
        threading.Thread(target=on_buffer_closing, args=(response, True)).start()
        return

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response['full_name'])

    if buffer_name is not None and buffer_name in slack_client.last_dm_channels:
        logging.info(f'Closing DM channel: {buffer_name}')

        slack_client.create_dm_channels([c for c in slack_client.last_dm_channels if c != buffer_name])


def on_slack_message(channel: str, msg: str):
    global relay_client

    weechat_channel = Utils.get_relay_direct_message_channel_for_buffer(channel)

    if weechat_channel is not None:
        relay_client.input(weechat_channel, msg)
    else:
        for weechat_channel, slack_channel in Config.Global.Channels.items():
            if slack_channel == channel:
                relay_client.input(weechat_channel, msg)
                break


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

    relay_client = RelayClient()
    relay_client.set_on_buffer_line_added_callback(on_buffer_line_added)
    relay_client.set_on_buffer_opened_callback_callback(on_buffer_opened)
    relay_client.set_on_buffer_closing_callback_callback(on_buffer_closing)

    slack_client = SlackClient()
    slack_client.set_message_callback(on_slack_message)
    slack_client.create_dm_channels([buffer for _, buffer in relay_client.get_direct_message_buffers()])

    threads = [
        *relay_client.tasks(),
        *slack_client.tasks(),
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
