import logging
import socket
import time
from threading import current_thread

import config
from pyweechat.pyweechat import WeeChatSocket, WeeChatMessage
from utils import Utils


class RelayClient:
    sock: WeeChatSocket

    def __init__(self):
        self.sock = WeeChatSocket(config.RELAY['hostname'], config.RELAY['port'], config.RELAY['use_ssl'])
        self.sock.connect(config.RELAY['password'])

        self.last_buffers = None

        self.ping()
        self.sync_all()

        # Trigger buffers update
        self.sock.send_async('hdata buffer:gui_buffers(*) full_name')

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
            raise Exception("Failed to receive pong back")

    def sync_all(self):
        self.sock.send_async('sync')
        self.sock.send_async('sync *')
        self.sock.send_async('sync * buffers,upgrade,buffer,nicklist')

    def get_direct_message_buffers(self):
        buffers = None

        while buffers is None:
            buffers = self.get_buffers()

        ret = []

        for channel in buffers:
            channel_name = Utils.get_slack_direct_message_channel_for_buffer(channel['full_name'])

            if channel_name is not None:
                ret.append((channel['full_name'], channel_name))

        return ret

    def get_buffers(self):
        self.sock.send_async('hdata buffer:gui_buffers(*) full_name')

        if self.last_buffers is None:
            logging.info("Waiting for initial buffers list")
            response = self.wait_for_response()

            if response is not None:
                buffers = response.get_hdata_result()

                if isinstance(buffers, list):
                    self.last_buffers = buffers

        return self.last_buffers

    def get_buffer_by_pointer(self, pointer: str):
        buffers = self.get_buffers()

        if buffers is not None:
            for buffer in buffers:
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
                logging.info("Updating buffers list")
                self.last_buffers = response.get_hdata_result()

            time.sleep(0.15)

        self.sock.disconnect()
