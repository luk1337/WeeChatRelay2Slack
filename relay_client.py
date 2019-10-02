import time
from threading import current_thread

import config
from pyweechat.pyweechat import WeeChatSocket
from utils import Utils


class RelayClient:
    sock: WeeChatSocket

    def __init__(self):
        self.sock = WeeChatSocket(config.RELAY['hostname'], config.RELAY['port'], config.RELAY['use_ssl'])
        self.sock.connect(config.RELAY['password'])

        self.last_buffers = None

        self.ping()
        self.sync_all()

    def wait_for_response(self, timeout=5):
        start = time.time()

        while time.time() < start + timeout:
            ret = self.sock.poll()

            if ret is not None:
                return ret

        return None

    def ping(self):
        self.sock.send_async('ping')

        if self.wait_for_response() is None:
            raise Exception("Failed to receive pong back")

    def sync_all(self):
        self.sock.send_async('sync')
        self.sock.send_async('sync *')
        self.sock.send_async('sync * buffers,upgrade,buffer,nicklist')

    def get_direct_message_buffers(self):
        buffers = self.get_buffers()

        if buffers is None:
            return None

        ret = []

        for channel in buffers:
            if 'full_name' not in channel:
                continue

            channel_name = Utils.get_slack_direct_message_channel_for_buffer(channel['full_name'])

            if channel_name is not None:
                ret.append((channel['full_name'], channel_name))

        return ret

    def get_buffers(self):
        self.sock.send_async('hdata buffer:gui_buffers(*) full_name')

        response = None

        # Pretend that this doesn't exist either
        try:
            response = self.wait_for_response()
        except RecursionError:
            pass

        if response is not None:
            buffers = response.get_hdata_result()

            if isinstance(buffers, list):
                self.last_buffers = buffers
                return buffers

        if self.last_buffers is not None:
            return self.last_buffers

        return None

    def get_buffer_by_full_name(self, full_name):
        buffers = self.get_buffers()

        if buffers is not None:
            for buffer in buffers:
                if buffer['__path'][0] == full_name:
                    return buffer

        return None

    def wait_for_buffer_by_full_name(self, full_name):
        buffer = None

        while buffer is None:
            buffer = self.get_buffer_by_full_name(full_name)
            time.sleep(0.1)

        return buffer

    def input(self, full_name, msg):
        self.sock.send_async('input {} {}'.format(full_name, msg))

    def run(self):
        while current_thread().is_alive:
            self.sock.poll()
            time.sleep(0.05)

        self.sock.disconnect()
