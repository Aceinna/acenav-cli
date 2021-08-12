"""
Communicator
"""
import os
import time
import json
import socket
import threading
from abc import ABCMeta, abstractmethod
import serial
import serial.tools.list_ports
from scapy.all import sendp, sniff, conf, AsyncSniffer
from scapy.layers.l2 import Ether
from ..devices import DeviceManager
from .constants import INTERFACES
from .context import APP_CONTEXT
from .utils.resource import get_executor_path
from .utils.print import (print_red, print_yellow)
from .utils import helper
from .wrapper import SocketConnWrapper


class CommunicatorFactory:
    '''
    Communicator Factory
    '''
    @staticmethod
    def create(method, options):
        '''
        Initial communicator instance
        '''
        if method == INTERFACES.ETH_100BASE_T1:
            return Ethernet(options)
        else:
            raise Exception('no matched communicator')


class Communicator(object):
    '''Communicator base
    '''
    __metaclass__ = ABCMeta

    def __init__(self):
        executor_path = get_executor_path()
        setting_folder_name = 'setting'
        self.setting_folder_path = os.path.join(
            executor_path, setting_folder_name)
        self.connection_file_path = os.path.join(
            self.setting_folder_path, 'connection.json')
        self.read_size = 0
        self.device = None
        self.threadList = []

    @abstractmethod
    def find_device(self, callback, retries=0, not_found_handler=None):
        '''
        find device, then invoke callback
        '''

    def open(self):
        '''
        open
        '''

    def close(self):
        '''
        close
        '''

    def write(self, data, is_flush=False):
        '''
        write
        '''

    def read(self, size):
        '''
        read
        '''

    def confirm_device(self, *args):
        '''
        validate the connected device
        '''
        device = None
        try:
            device = DeviceManager.ping(self, *args)
        except Exception as ex:
            APP_CONTEXT.get_logger().logger.info('Error while confirm device %s', ex)
            device = None
        if device and not self.device:
            self.device = device
            return True
        return False


class StoppableThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class Ethernet(Communicator):
    '''Ethernet'''

    def __init__(self, options=None):
        super().__init__()
        self.type = INTERFACES.ETH_100BASE_T1
        self.src_mac = None
        self.dst_mac = 'FF:FF:FF:FF:FF:FF'
        self.ethernet_name = None
        self.data = None
        self.iface = None

        self.filter_device_type = None
        self.filter_device_type_assigned = False

        self.iface_confirmed = False

        if options and options.device_type != 'auto':
            self.filter_device_type = options.device_type
            self.filter_device_type_assigned = True

    def handle_receive_packet(self, packet):
        self.iface_confirmed = True
        self.dst_mac = packet.src

    def confirm_iface(self, iface):
        pG = [0x01, 0xcc]
        filter_exp = 'ether dst host ' + \
            iface[1] + ' and ether[16:2] == 0x01cc'
        src_mac = bytes([int(x, 16) for x in iface[1].split(':')])
        command_line = helper.build_ethernet_packet(
            self.get_dst_mac(), src_mac, pG)
        async_sniffer = AsyncSniffer(
            iface=iface[0], prn=self.handle_receive_packet, filter=filter_exp)
        async_sniffer.start()
        time.sleep(.2)
        sendp(command_line, iface=iface[0], verbose=0)
        time.sleep(.5)
        async_sniffer.stop()

        if self.iface_confirmed:
            self.iface = iface[0]
            self.src_mac = iface[1]
            print('[NetworkCard]', self.iface, 'MAC:',self.src_mac)

    def find_device(self, callback, retries=0, not_found_handler=None):
        self.device = None
        self.iface_confirmed = False

        # find network connection
        ifaces_list = self.get_network_card()
        for i in range(len(ifaces_list)):
            self.confirm_iface(ifaces_list[i])
            if self.iface_confirmed:
                break
            else:
                if i == len(ifaces_list) - 1:
                    print('No available Ethernet card was found.')
                    return None

        # confirm device
        time.sleep(1)
        self.confirm_device(self)
        if self.device:
            callback(self.device)

    def open(self):
        '''
        open
        '''

    def close(self):
        '''
        close
        '''

    def can_write(self):
        if self.iface:
            return True
        return False

    def write(self, data, is_flush=False):
        '''
        write
        '''
        try:
            sendp(data, iface=self.iface, verbose=0)
            # print(data)
        except Exception as e:
            raise

    def read(self, callback=None):
        '''
        read
        '''
        filter_exp = 'ether src host ' + self.dst_mac
        sniff(store=0, prn=callback, count=0, iface=self.iface, filter=filter_exp)

    def handle_receive_read_result(self, packet):
        self.read_result = bytes(packet)

    def write_read(self, data, filter_cmd_type=0):
        if filter_cmd_type:
            filter_exp = 'ether dst host ' + self.src_mac + \
                ' and ether[16:2] == %d' % filter_cmd_type
        else:
            filter_exp = 'ether dst host ' + self.src_mac

        self.read_result = None
        async_sniffer = AsyncSniffer(
            iface=self.iface, prn=self.handle_receive_read_result, filter=filter_exp)
        async_sniffer.start()
        time.sleep(.2)
        sendp(data, iface=self.iface, verbose=0)
        time.sleep(.5)
        async_sniffer.stop()

        if self.read_result:
            return self.read_result

        return None

    def reset_buffer(self):
        '''
        reset buffer
        '''
        pass

    def get_src_mac(self):
        return bytes([int(x, 16) for x in self.src_mac.split(':')])

    def get_dst_mac(self):
        return bytes([int(x, 16) for x in self.dst_mac.split(':')])

    def get_network_card(self):
        network_card_info = []
        for item in conf.ifaces:
            if conf.ifaces[item].ip == '127.0.0.1' or conf.ifaces[item].mac == '':
                continue
            network_card_info.append(
                (conf.ifaces[item].name, conf.ifaces[item].mac))
        return network_card_info
