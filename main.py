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

    buffer = relay_client.get_buffer_by_full_name(e['buffer'])

    if buffer is None:
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
            slack_client.send_message(buffer_name, nick, msg)


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


def sync_direct_message_buffers():
    global relay_client, slack_client

    while threading.current_thread().is_alive:
        # Update direct message buffers every 15 seconds
        if time.time() % 15.0 <= 0.05:
            buffers = relay_client.get_direct_message_buffers()

            if buffers is not None:
                slack_client.create_dm_channels([buffer.lower() for _, buffer in buffers])

        time.sleep(0.05)


if __name__ == '__main__':
    # Uncomment if needed
    # logging.basicConfig(level=logging.DEBUG)

    relay_client = RelayClient()
    relay_client.sock.on('buffer_line_added', on_buffer_line_added)

    slack_client = SlackClient()
    slack_client.set_message_callback(on_slack_message)

    threads = [
        threading.Thread(target=relay_client.run),
        threading.Thread(target=slack_client.kill_me),
        threading.Thread(target=slack_client.run),
        threading.Thread(target=sync_direct_message_buffers),
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
