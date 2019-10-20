import re

from config import Config


class Utils:
    GUI_COLOR_COLOR_CHAR = '\x19'
    GUI_COLOR_SET_ATTR_CHAR = '\x1A'
    GUI_COLOR_REMOVE_ATTR_CHAR = '\x1B'
    GUI_COLOR_RESET_CHAR = '\x1C'

    GUI_COLOR_FG_CHAR = 'F'
    GUI_COLOR_BG_CHAR = 'B'
    GUI_COLOR_FG_BG_CHAR = '*'
    GUI_COLOR_EXTENDED_CHAR = '@'
    GUI_COLOR_EXTENDED_BOLD_CHAR = '*'
    GUI_COLOR_EXTENDED_REVERSE_CHAR = '!'
    GUI_COLOR_EXTENDED_ITALIC_CHAR = '/'
    GUI_COLOR_EXTENDED_UNDERLINE_CHAR = '_'
    GUI_COLOR_EXTENDED_KEEPATTR_CHAR = '|'
    GUI_COLOR_EMPHASIS_CHAR = 'E'

    GUI_COLOR_BAR_CHAR = 'b'
    GUI_COLOR_BAR_FG_CHAR = 'F'
    GUI_COLOR_BAR_DELIM_CHAR = 'D'
    GUI_COLOR_BAR_BG_CHAR = 'B'
    GUI_COLOR_BAR_START_INPUT_CHAR = '_'
    GUI_COLOR_BAR_START_INPUT_HIDDEN_CHAR = '-'
    GUI_COLOR_BAR_MOVE_CURSOR_CHAR = '#'
    GUI_COLOR_BAR_START_ITEM = 'i'
    GUI_COLOR_BAR_START_LINE_ITEM = 'l'

    GUI_COLOR_EXTENDED_FLAG = 0x0100000
    GUI_COLOR_EXTENDED_BOLD_FLAG = 0x0200000
    GUI_COLOR_EXTENDED_REVERSE_FLAG = 0x0400000
    GUI_COLOR_EXTENDED_ITALIC_FLAG = 0x0800000
    GUI_COLOR_EXTENDED_UNDERLINE_FLAG = 0x1000000
    GUI_COLOR_EXTENDED_KEEPATTR_FLAG = 0x2000000
    GUI_COLOR_EXTENDED_MASK = 0x00FFFFF
    GUI_COLOR_EXTENDED_MAX = 99999

    @staticmethod
    def sanitize_slack_channel_name(full_name: str, prefix_length: int):
        # According to slack channel names can only contain lowercase letters,
        # numbers, hyphens, and underscores, and must be 80 characters or less.
        return re.sub(r'[^a-z0-9-_&#]', '_', full_name[prefix_length:prefix_length + 80].lower())

    @staticmethod
    def get_relay_direct_message_channel_for_buffer(full_name: str):
        for weechat_prefix, slack_prefix in Config.Global.PrivMsgs.items():
            if full_name.startswith(slack_prefix):
                return weechat_prefix + Utils.sanitize_slack_channel_name(full_name, len(slack_prefix))

        return None

    @staticmethod
    def get_slack_direct_message_channel_for_buffer(full_name: str):
        for weechat_prefix, slack_prefix in Config.Global.PrivMsgs.items():
            if not full_name.startswith(weechat_prefix):
                continue

            name = Utils.sanitize_slack_channel_name(full_name, len(weechat_prefix))

            # According to RFC 1459 channels are supposed to start with '&' or '#'
            if not any(name.startswith(char) for char in ['&', '#']):
                return slack_prefix + name

        return None

    @staticmethod
    def gui_color_attr_get_flag(string: str):
        flags = {
            Utils.GUI_COLOR_EXTENDED_BOLD_CHAR: Utils.GUI_COLOR_EXTENDED_BOLD_FLAG,
            Utils.GUI_COLOR_EXTENDED_REVERSE_CHAR: Utils.GUI_COLOR_EXTENDED_REVERSE_FLAG,
            Utils.GUI_COLOR_EXTENDED_ITALIC_CHAR: Utils.GUI_COLOR_EXTENDED_ITALIC_FLAG,
            Utils.GUI_COLOR_EXTENDED_UNDERLINE_CHAR: Utils.GUI_COLOR_EXTENDED_UNDERLINE_FLAG,
            Utils.GUI_COLOR_EXTENDED_KEEPATTR_CHAR: Utils.GUI_COLOR_EXTENDED_KEEPATTR_FLAG,
        }

        if string in flags:
            return flags[string]

        return 0

    @staticmethod
    def weechat_string_remove_color(string: str):
        s = list(string)
        length = len(s)

        i = 0
        buf = ''

        while i < length:
            if s[i] == Utils.GUI_COLOR_COLOR_CHAR:
                i += 1

                if s[i] == Utils.GUI_COLOR_FG_CHAR:
                    i += 1

                    if s[i] == Utils.GUI_COLOR_EXTENDED_CHAR:
                        i += 1

                        while Utils.gui_color_attr_get_flag(s[i]) > 0:
                            i += 1

                        if i + 4 < length:
                            i += 5
                    else:
                        while Utils.gui_color_attr_get_flag(s[i]) > 0:
                            i += 1

                        if i + 1 < length:
                            i += 2
                elif s[i] == Utils.GUI_COLOR_BG_CHAR:
                    i += 1

                    if s[i] == Utils.GUI_COLOR_EXTENDED_CHAR:
                        i += 1

                        if i + 4 < length:
                            i += 5
                    else:
                        if i + 1 < length:
                            i += 2
                elif s[i] == Utils.GUI_COLOR_FG_BG_CHAR:
                    i += 1

                    if s[i] == Utils.GUI_COLOR_EXTENDED_CHAR:
                        i += 1

                        while Utils.gui_color_attr_get_flag(s[i]) > 0:
                            i += 1

                        if i + 4 < length:
                            i += 5
                    else:
                        while Utils.gui_color_attr_get_flag(s[i]) > 0:
                            i += 1

                        if i + 1 < length:
                            i += 2

                    # note: the comma is an old separator not used any
                    # more (since WeeChat 2.6), but we still use it here
                    # so in case of/upgrade this will not break colors in
                    # old messages
                    if i < length:
                        if s[i] == ',' or s[i] == '~':
                            if s[i + 1] == Utils.GUI_COLOR_EXTENDED_CHAR:
                                i += 2

                                if i + 4 < length:
                                    i += 5
                            else:
                                i += 1

                                if i + 1 < length:
                                    i += 2
                elif s[i] == Utils.GUI_COLOR_EXTENDED_CHAR:
                    i += 1

                    if i + 4 < length and all(x.isdigit() for x in s[i:i + 5]):
                        i += 5
                elif s[i] == Utils.GUI_COLOR_EMPHASIS_CHAR:
                    i += 1
                elif s[i] == Utils.GUI_COLOR_BAR_CHAR:
                    i += 1

                    if s[i] in [Utils.GUI_COLOR_BAR_FG_CHAR,
                                Utils.GUI_COLOR_BAR_BG_CHAR,
                                Utils.GUI_COLOR_BAR_DELIM_CHAR,
                                Utils.GUI_COLOR_BAR_START_INPUT_CHAR,
                                Utils.GUI_COLOR_BAR_START_INPUT_HIDDEN_CHAR,
                                Utils.GUI_COLOR_BAR_MOVE_CURSOR_CHAR,
                                Utils.GUI_COLOR_BAR_START_ITEM,
                                Utils.GUI_COLOR_BAR_START_LINE_ITEM]:
                        i += 1
                elif s[i] == Utils.GUI_COLOR_RESET_CHAR:
                    i += 1
                else:
                    if all(x.isdigit() for x in s[i:i + 1]):
                        i += 2
            elif s[i] in [Utils.GUI_COLOR_SET_ATTR_CHAR, Utils.GUI_COLOR_REMOVE_ATTR_CHAR]:
                i += 1

                if i < length:
                    i += 1
            elif s[i] == Utils.GUI_COLOR_RESET_CHAR:
                i += 1
            else:
                buf += s[i]
                i += 1

        return buf
