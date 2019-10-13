import time
from datetime import timedelta
from threading import current_thread

from config import Config
from pyweechat.pyweechat import WeeChatClient, WeeChatBuffer
from utils import Utils


class RelayClient(WeeChatClient):
    on_buffer_line_added_callback: callable
    on_buffer_opened_callback: callable
    on_buffer_closing_callback: callable

    def __init__(self):
        super().__init__(hostname=Config.Relay.Hostname,
                         password=Config.Relay.Password,
                         port=Config.Relay.Port,
                         use_ssl=Config.Relay.UseSSL)

    def _setup(self):
        self._setup_buffers()

        # Setup event handling only after reading buffers completed
        self.socket.on('buffer_line_added', self._on_buffer_line_added)
        self.socket.on('buffer_opened', self._on_buffer_opened)
        self.socket.on('buffer_closing', self._on_buffer_closing)

        # Turn synchronization on for all channels
        self.sync('*')

    def _setup_buffers(self):
        pointer = 'gui_buffers'

        while True:
            # Read meta information
            resp_buf = self.socket.send('hdata buffer:{}'.format(pointer)).get_hdata_result()

            if resp_buf is None:
                break

            buffer = WeeChatBuffer(resp_buf)
            buffer.pointer = pointer

            self.buffers.append(buffer)

            if resp_buf.get('next_buffer') is None or resp_buf.get('next_buffer') == '0':
                break

            pointer = '0x{}'.format(resp_buf.get('next_buffer'))

    def _on_buffer_line_added(self, response: dict):
        if self.on_buffer_line_added_callback is not None:
            self.on_buffer_line_added_callback(response)

        # super()._on_buffer_line_added(response)

    def _on_buffer_opened(self, response: dict):
        if self.on_buffer_opened_callback is not None:
            self.on_buffer_opened_callback(response)

        super()._on_buffer_opened(response)

    def _on_buffer_closing(self, response: dict):
        if self.on_buffer_closing_callback is not None:
            self.on_buffer_closing_callback(response)

        super()._on_buffer_closing(response)

    def set_on_buffer_line_added_callback(self, f: callable):
        self.on_buffer_line_added_callback = f

    def set_on_buffer_opened_callback_callback(self, f: callable):
        self.on_buffer_opened_callback = f

    def set_on_buffer_closing_callback_callback(self, f: callable):
        self.on_buffer_closing_callback = f

    def get_direct_message_buffers(self):
        ret = []

        for channel in self.buffers:
            channel_name = Utils.get_slack_direct_message_channel_for_buffer(channel.full_name)

            if channel_name is not None:
                ret.append((channel.full_name, channel_name))

        return ret

    def wait_for_buffer_by_pointer(self, pointer: str, timeout: int = 5):
        buffer = None
        start = time.time()

        while time.time() < start + timeout and buffer is None:
            buffer = self.get_buffer_by_pointer(pointer)
            time.sleep(0.15)

        return buffer

    def run_thread(self):
        self.run(lambda: current_thread().is_alive, timedelta(milliseconds=100))
