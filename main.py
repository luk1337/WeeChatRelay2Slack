import sys
import threading
import time

import config
from relay_client import RelayClient
from slack_client import SlackClient
from utils import Utils

# globals
relay_client: RelayClient
slack_client: SlackClient


def on_buffer_line_added(e):
    global relay_client, slack_client

    if 'irc_privmsg' not in e['tags_array']:
        return

    buffer = relay_client.wait_for_buffer_by_full_name(e['buffer'])

    if 'full_name' not in buffer:
        return

    for tag in e['tags_array']:
        if tag.startswith("nick_"):
            nick = tag[5:]
            break
    else:
        return

    buffer_name, msg = buffer['full_name'], e['message']

    if buffer_name in config.GLOBAL['channels']:
        slack_client.send_message(config.GLOBAL['channels'][buffer_name], nick, msg)
    else:
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

        if buffer_name is not None:
            # Wait for slack channel
            while buffer_name not in slack_client.last_dm_channels:
                pass

            if 'irc_action' in e['tags_array']:
                slack_client.send_me_message(buffer_name, nick, msg.split(' ', 1)[1])
            else:
                slack_client.send_message(buffer_name, nick, msg)


def on_buffer_opened(e):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(e['full_name'])

    if buffer_name is not None and buffer_name not in slack_client.last_dm_channels:
        slack_client.create_dm_channels(slack_client.last_dm_channels + [buffer_name])


def on_buffer_closing(e):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(e['full_name'])

    if buffer_name is not None and buffer_name in slack_client.last_dm_channels:
        slack_client.last_dm_channels.remove(buffer_name)
        slack_client.clean_up_dm_channels(slack_client.last_dm_channels)


def on_slack_message(channel, msg):
    global relay_client

    weechat_channel = Utils.get_relay_direct_message_channel_for_buffer(channel)

    if weechat_channel is not None:
        relay_client.input(weechat_channel, msg)
    else:
        for weechat_channel, slack_channel in config.GLOBAL['channels'].items():
            if slack_channel == channel:
                relay_client.input(weechat_channel, msg)
                break


def create_direct_message_channels():
    buffers = None

    while buffers is None:
        buffers = relay_client.get_direct_message_buffers()
        time.sleep(0.1)

    slack_client.create_dm_channels([buffer.lower() for _, buffer in buffers])


if __name__ == '__main__':
    # Uncomment if needed
    # logging.basicConfig(level=logging.DEBUG)

    relay_client = RelayClient()
    relay_client.sock.on('buffer_line_added', on_buffer_line_added)
    relay_client.sock.on('buffer_opened', on_buffer_opened)
    relay_client.sock.on('buffer_closing', on_buffer_closing)

    slack_client = SlackClient()
    slack_client.set_message_callback(on_slack_message)

    create_direct_message_channels()

    threads = [
        threading.Thread(target=relay_client.run),
        threading.Thread(target=slack_client.kill_me),
        threading.Thread(target=slack_client.run),
    ]

    [thread.start() for thread in threads]

    try:
        [thread.join() for thread in threads]
    except KeyboardInterrupt:
        # Kill existing threads
        for thread in threads:
            thread.is_alive = False
            thread.join()

        sys.exit()
