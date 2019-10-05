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


def on_buffer_line_added(response: dict):
    global relay_client, slack_client

    is_401 = 'irc_401' in response['tags_array']
    is_402 = 'irc_402' in response['tags_array']
    is_kick = 'irc_kick' in response['tags_array']
    is_join = 'irc_join' in response['tags_array']
    is_part_or_quit = 'irc_part' in response['tags_array'] or 'irc_quit' in response['tags_array']
    is_privmsg = 'irc_privmsg' in response['tags_array']

    if not any((is_401, is_402, is_kick, is_join, is_part_or_quit, is_privmsg)):
        return

    buffer = relay_client.wait_for_buffer_by_pointer(response['buffer'])
    buffer_name, msg = buffer['full_name'], response['message']

    if buffer_name not in Config.Global.Channels:
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

        if buffer_name is not None:
            # Wait for slack channel
            while buffer_name not in slack_client.last_dm_channels:
                pass
    else:
        buffer_name = Config.Global.Channels[buffer_name]

    if buffer_name is not None:
        if any([is_401, is_402, is_kick, is_join, is_part_or_quit]):
            slack_client.send_me_message(buffer_name, Utils.weechat_string_remove_color(response['message']))
        elif is_privmsg:
            prefix = Utils.weechat_string_remove_color(response['prefix'])

            if 'irc_action' in response['tags_array']:
                slack_client.send_me_message(buffer_name, '*{}* {}'.format(prefix, msg.split(' ', 1)[1]))
            else:
                slack_client.send_message(buffer_name, prefix, msg)


def on_buffer_opened(response: dict):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response['full_name'])

    if buffer_name is not None and buffer_name not in slack_client.last_dm_channels:
        logging.info('Adding DM channel: {}'.format(buffer_name))

        slack_client.create_dm_channels(slack_client.last_dm_channels + [buffer_name])


def on_buffer_closing(response: dict):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(response['full_name'])

    if buffer_name is not None and buffer_name in slack_client.last_dm_channels:
        logging.info('Closing DM channel: {}'.format(buffer_name))

        slack_client.last_dm_channels.remove(buffer_name)
        slack_client.clean_up_dm_channels(slack_client.last_dm_channels)


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
    relay_client.sock.on('buffer_line_added', on_buffer_line_added)
    relay_client.sock.on('buffer_opened', on_buffer_opened)
    relay_client.sock.on('buffer_closing', on_buffer_closing)

    slack_client = SlackClient()
    slack_client.set_message_callback(on_slack_message)
    slack_client.create_dm_channels([buffer for _, buffer in relay_client.get_direct_message_buffers()])

    threads = [
        threading.Thread(target=relay_client.run),
        threading.Thread(target=slack_client.kill_me),
        threading.Thread(target=slack_client.run),
    ]

    [thread.start() for thread in threads]

    try:
        [thread.join() for thread in threads]
    except KeyboardInterrupt:
        logging.info("Bye!")

        # Kill existing threads
        for thread in threads:
            thread.is_alive = False
            thread.join()
