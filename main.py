import logging
import threading

import config
from relay_client import RelayClient
from slack_client import SlackClient
from utils import Utils

# globals
relay_client: RelayClient
slack_client: SlackClient


def on_buffer_line_added(e):
    global relay_client, slack_client

    is_401 = 'irc_401' in e['tags_array']
    is_402 = 'irc_402' in e['tags_array']
    is_join = 'irc_join' in e['tags_array']
    is_part_or_quit = 'irc_part' in e['tags_array'] or 'irc_quit' in e['tags_array']
    is_privmsg = 'irc_privmsg' in e['tags_array']

    if not any((is_401, is_402, is_join, is_part_or_quit, is_privmsg)):
        return

    buffer = relay_client.wait_for_buffer_by_full_name(e['buffer'])

    for tag in e['tags_array']:
        if tag.startswith('nick_'):
            nick = tag[5:]
            break
    else:
        # 401, 402 don't put nick_{} in tags
        if not any((is_401, is_402)):
            return

    buffer_name, msg = buffer['full_name'], e['message']

    if buffer_name not in config.GLOBAL['channels']:
        buffer_name = Utils.get_slack_direct_message_channel_for_buffer(buffer_name)

        if buffer_name is not None:
            # Wait for slack channel
            while buffer_name not in slack_client.last_dm_channels:
                pass
    else:
        buffer_name = config.GLOBAL['channels'][buffer_name]

    if buffer_name is not None:
        if is_401:
            slack_client.send_me_message(buffer_name, 'No such nick/channel')
        elif is_402:
            slack_client.send_me_message(buffer_name, 'No such server')
        elif is_join:
            slack_client.send_me_message(buffer_name, '*{}* joined'.format(nick))
        elif is_part_or_quit:
            slack_client.send_me_message(buffer_name, '*{}* left'.format(nick))
        elif is_privmsg:
            if 'irc_action' in e['tags_array']:
                slack_client.send_me_message(buffer_name, '*{}* {}'.format(nick, msg.split(' ', 1)[1]))
            else:
                slack_client.send_message(buffer_name, nick, msg)


def on_buffer_opened(e):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(e['full_name'])

    if buffer_name is not None and buffer_name not in slack_client.last_dm_channels:
        logging.info('Adding DM channel: {}'.format(buffer_name))

        slack_client.create_dm_channels(slack_client.last_dm_channels + [buffer_name])


def on_buffer_closing(e):
    global slack_client

    buffer_name = Utils.get_slack_direct_message_channel_for_buffer(e['full_name'])

    if buffer_name is not None and buffer_name in slack_client.last_dm_channels:
        logging.info('Closing DM channel: {}'.format(buffer_name))

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
