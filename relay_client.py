import logging
import socket
import time
from threading import current_thread

from config import Config
from pyweechat.pyweechat import WeeChatSocket, WeeChatMessage
from utils import Utils


class RelayClient:
    sock: WeeChatSocket
    last_buffers: dict

    def __init__(self):
        self.sock = WeeChatSocket(Config.Relay.Hostname, Config.Relay.Port, Config.Relay.UseSSL)
        self.sock.connect(Config.Relay.Password)

        self.ping()

        self.last_buffers = self.sock.send('hdata buffer:gui_buffers(*) full_name').get_hdata_result()

        self.sync_all()

    def wait_for_response(self, timeout: int = 5):
        start = time.time()

        while time.time() < start + timeout:
            try:
                response = self.sock.socket.recv(4096 * 1024)

                if response:
                    return WeeChatMessage(response)
            except socket.error as e:
                pass

        return None

    def ping(self):
        self.sock.send_async('ping')

        if self.wait_for_response() is None:
            raise Exception('Failed to receive pong back')

    def sync_all(self):
        self.sock.send_async('sync')
        self.sock.send_async('sync *')
        self.sock.send_async('sync * buffers,upgrade,buffer,nicklist')

    def get_direct_message_buffers(self):
        ret = []

        for channel in self.get_buffers():
            channel_name = Utils.get_slack_direct_message_channel_for_buffer(channel['full_name'])

            if channel_name is not None:
                ret.append((channel['full_name'], channel_name))

        return ret

    def get_buffers(self):
        self.sock.send_async('hdata buffer:gui_buffers(*) full_name')
        return self.last_buffers

    def get_buffer_by_pointer(self, pointer: str):
        for buffer in self.get_buffers():
            if buffer['__path'][0] == pointer:
                return buffer

        return None

    def wait_for_buffer_by_pointer(self, pointer: str):
        buffer = None

        while buffer is None:
            buffer = self.get_buffer_by_pointer(pointer)
            time.sleep(0.15)

        return buffer

    def input(self, full_name: str, msg: str):
        self.sock.send_async('input {} {}'.format(full_name, msg))

    def run(self):
        while current_thread().is_alive:
            response = self.sock.poll()

            if response is not None and not response.id:
                logging.info('Updating buffers list')
                self.last_buffers = response.get_hdata_result()

            time.sleep(0.15)

        self.sock.disconnect()
