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
            '\x19F12luk\x1928 (\x1927~luk@kremowka.xyz\x1928)\x19F05 has joined \x1913#titandev-test\x19F05'),
            'luk (~luk@kremowka.xyz) has joined #titandev-test')
        self.assertEqual(Utils.weechat_string_remove_color(
            '\x19F12luk\x1928 (\x1927~luk@kremowka.xyz\x1928)\x19F03 has left \x1913#titandev-test\x19F03'),
            'luk (~luk@kremowka.xyz) has left #titandev-test')
        self.assertEqual(Utils.weechat_string_remove_color(
            '\x19F12luk\x1928 (\x1927~luk@kremowka.xyz\x1928)\x19F03 has quit \x1928(\x19F00Client Quit\x1928)'),
            'luk (~luk@kremowka.xyz) has quit (Client Quit)')
        self.assertEqual(Utils.weechat_string_remove_color(
            '\x1915LuK1337\x19F03 has kicked \x19F12luk\x19F03 \x1928(\x1cluk\x1928)'),
            'LuK1337 has kicked luk (luk)')
        self.assertEqual(Utils.weechat_string_remove_color(
            '\x1915LuK1337\x1c has changed topic for \x1913#titandev-test\x1c from "hi\x1c" to "\x19F16hello\x1c"'),
            'LuK1337 has changed topic for #titandev-test from "hi" to "hello"')
        self.assertEqual(Utils.weechat_string_remove_color(
            'Mode \x1913#titandev-test \x1928[\x1c+r\x1928]\x1c by \x1915LuK1337'),
            'Mode #titandev-test [+r] by LuK1337')


if __name__ == '__main__':
    unittest.main()
