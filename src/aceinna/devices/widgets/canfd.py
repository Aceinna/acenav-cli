from __future__ import print_function
from logging import exception
import can
from can.bus import BusState
from queue import Queue
import os
from time import sleep
import signal
from ...core.event_base import EventBase


class canfd_config:
    _channel: str
    _bitrate: int

    def __init__(self, bustype: str, channel: int, bitrate: int, data_bitrate: int) -> None:
        self._bustype = bustype
        self._channel = channel
        self._bitrate = bitrate
        self._data_bitrate = data_bitrate

    @property
    def bustype(self):
        return self._bustype

    @property
    def channel(self):
        return self._channel

    @property
    def bitrate(self):
        return self._bitrate

    @property
    def data_bitrate(self):
        return self._data_bitrate

class canfd(EventBase):
    def __init__(self, options: canfd_config):
        super(canfd, self).__init__()

        # if 'Linux' in platform.system():
        #     DLL_NAME = 'libbmapi64.so' if platform.architecture()[0] == '64bit' else 'libbmapi.so'
        # else:
        #     DLL_NAME = './bmapi64.dll' if platform.architecture()[0] == '64bit' else './bmapi.dll'
        # bmapi_dll = ctypes.cdll.LoadLibrary(DLL_NAME)
        self.bustype = options.bustype
        self.channel = options.channel
        self.bitrate = options.bitrate
        self.data_bitrate = options.data_bitrate
        self.bus = can.interface.Bus(bustype=self.bustype, channel=self.channel, bitrate=self.bitrate, data_bitrate=self.data_bitrate, tres=True)        

    def canfd_bus_active(self):
        self.bus.state = BusState.ACTIVE
    def write(self, id, data, is_extended_id=False, is_fd=True):
        msg = can.Message(  arbitration_id=id,
                            data=data,
                            is_extended_id=is_extended_id,
                            is_fd=is_fd)
        try:
            self.bus.send(msg, timeout=None)
        except Exception as e:
            print(e)
    def read(self, timeout=None):
        msg = self.bus.recv(timeout=0.1)
        return msg


def kill_app(signal_int, call_back):
    '''Kill main thread
    '''
    os.kill(os.getpid(), signal.SIGTERM)

'''
if __name__ == "__main__":
    if len(sys.argv) < 2:
        json_config = "ins_canfd.json"
    else:
        json_config = sys.argv[1]
    signal.signal(signal.SIGINT, kill_app)
    day = get_utc_day()
    mkpath='./' + day
    path = mkdir(mkpath)    
    canfd_parser = ins401_canfd_driver(mkpath, json_config)
    canfd_parser.start_pasre()
'''