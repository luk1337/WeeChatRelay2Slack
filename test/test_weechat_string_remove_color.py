import unittest

from utils import Utils


class TestWeeChatStringRemoveColor(unittest.TestCase):
    def test(self):
        self.assertEqual(Utils.weechat_string_remove_color(''), '')

        self.assertEqual(Utils.weechat_string_remove_color('\x1901'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19@00001'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19F*05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19@00214'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19B05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19B@00124'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*@00214'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*08,05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*01,@00214'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*@00214,05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*@00214,@00017'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*08~05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*01~@00214'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*@00214~05'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19*@00214~@00017'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19bF'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19bD'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19bB'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19b_'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19b-'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19b#'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19bi'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19bl'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19E'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x19\x1C'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x1A*'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x1A_'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x1B*'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x1B_'), '')
        self.assertEqual(Utils.weechat_string_remove_color('\x1C'), '')

        self.assertEqual(Utils.weechat_string_remove_color(
            'Mode \x1913#titandev-test \x1928[\x1c+q a!*@*\x1928]\x1c by \x1915LuK1337'),
            'Mode #titandev-test [+q a!*@*] by LuK1337')


if __name__ == '__main__':
    unittest.main()
