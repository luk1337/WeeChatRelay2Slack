import logging
import socket
import time
from threading import current_thread

from config import Config
from pyweechat.pyweechat import WeeChatSocket, WeeChatMessage
from utils import Utils


class RelayClient:
    sock: WeeChatSocket
    buffers: dict

    def __init__(self):
        self.sock = WeeChatSocket(Config.Relay.Hostname, Config.Relay.Port, Config.Relay.UseSSL)
        self.sock.connect(Config.Relay.Password)

        self.ping()

        self.buffers = self.sock.send('hdata buffer:gui_buffers(*) full_name').get_hdata_result()

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

        for buffer in self.buffers:
            channel_name = Utils.get_slack_direct_message_channel_for_buffer(buffer['full_name'])

            if channel_name is not None:
                ret.append((buffer['full_name'], channel_name))

        return ret

    def get_buffer_by_pointer(self, pointer: str):
        # Try to find buffer in current buffers list
        for buffer in self.buffers:
            if buffer['__path'][0] == pointer:
                return buffer

        # Update buffers just in case
        self.buffers = self.sock.send('hdata buffer:gui_buffers(*) full_name').get_hdata_result()

        # Retry
        for buffer in self.buffers:
            if buffer['__path'][0] == pointer:
                return buffer

        return None

    def wait_for_buffer_by_pointer(self, pointer: str, timeout: int = 5):
        buffer = None
        start = time.time()

        while time.time() < start + timeout and buffer is None:
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
                self.buffers = response.get_hdata_result()

            time.sleep(0.15)

        self.sock.disconnect()
