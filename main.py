import logging
import sys
import threading

import config
from relay_client import RelayClient
from slack_client import SlackClient

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

    nick = None

    for tag in e['tags_array']:
        if tag.startswith("nick_"):
            nick = tag[5:]

    if nick is None:
        return

    buffer_name, msg = buffer['full_name'], e['message']

    if buffer_name in config.GLOBAL['channels']:
        slack_client.send_message(config.GLOBAL['channels'][buffer_name], nick, msg)


def on_slack_message(channel, msg):
    global relay_client

    for weechat_channel, slack_channel in config.GLOBAL['channels'].items():
        if slack_channel == channel:
            relay_client.input(weechat_channel, msg)
            break


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
