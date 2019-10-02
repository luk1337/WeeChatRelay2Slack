import re

import config


class Utils:
    @staticmethod
    def sanitize_slack_channel_name(full_name: str, prefix_length: int):
        # According to slack channel names can only contain lowercase letters,
        # numbers, hyphens, and underscores, and must be 80 characters or less.
        return re.sub(r'[^a-z-_&#]', "_", full_name[prefix_length:prefix_length + 80].lower())

    @staticmethod
    def get_relay_direct_message_channel_for_buffer(full_name: str):
        for weechat_prefix, slack_prefix in config.GLOBAL['privmsgs'].items():
            if full_name.startswith(slack_prefix):
                return weechat_prefix + Utils.sanitize_slack_channel_name(full_name, len(slack_prefix))

        return None

    @staticmethod
    def get_slack_direct_message_channel_for_buffer(full_name: str):
        for weechat_prefix, slack_prefix in config.GLOBAL['privmsgs'].items():
            if not full_name.startswith(weechat_prefix):
                continue

            name = Utils.sanitize_slack_channel_name(full_name, len(weechat_prefix))

            # According to RFC 1459 channels are supposed to start with '&' or '#'
            if not any(name.startswith(char) for char in ['&', '#']):
                return slack_prefix + name

        return None
