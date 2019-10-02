import time
from threading import current_thread

import config
from pyweechat.pyweechat import WeeChatSocket


class RelayClient:
    sock: WeeChatSocket

    def __init__(self):
        self.sock = WeeChatSocket(config.RELAY['hostname'], config.RELAY['port'], config.RELAY['use_ssl'])
        self.sock.connect(config.RELAY['password'])

        for channel in config.GLOBAL['channels']:
            self.sock.send_async('sync {}'.format(channel))

    def get_buffers(self):
        self.sock.send_async('hdata buffer:gui_buffers(*) full_name')

        while True:
            ret = self.sock.poll()

            if ret is not None:
                buffers = ret.get_hdata_result()

                if isinstance(buffers, list):
                    return buffers

                return []

    def get_buffer_by_full_name(self, full_name):
        for buffer in self.get_buffers():
            if buffer['__path'][0] == full_name:
                return buffer

        return None

    def input(self, full_name, msg):
        self.sock.send_async('input {} {}'.format(full_name, msg))

    def run(self):
        while current_thread().is_alive:
            self.sock.poll()
            time.sleep(0.05)

        self.sock.disconnect()
