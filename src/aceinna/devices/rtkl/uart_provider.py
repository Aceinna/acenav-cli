import time
import serial
import struct

from ..base.rtk_provider_base import RTKProviderBase
from ..base.beidou_provider_base import beidouProviderBase
from ..upgrade_workers import (
    FirmwareUpgradeWorker,
    SDK9100UpgradeWorker,
    UPGRADE_EVENT,
    UPGRADE_GROUP
)
from ...framework.utils import (
    helper
)
from ...framework.utils.print import print_red


class Provider(RTKProviderBase):
    '''
    RTK330LA UART provider
    '''

    def __init__(self, communicator, *args):
        super(Provider, self).__init__(communicator)
        self.type = 'RTKL'
        self.bootloader_baudrate = 115200
        self.config_file_name = 'RTK330L.json'
        self.device_category = 'RTK330LA'
        self.port_index_define = {
            'user': 0,
            'rtcm': 3,
            'debug': 2,
        }

    def thread_debug_port_receiver(self, *args, **kwargs):
        if self.debug_logf is None:
            return

        # log data
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.debug_serial_port.read_all())
            except Exception as e:
                print_red('DEBUG PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if data and len(data) > 0:
                self.debug_logf.write(data)
            else:
                time.sleep(0.001)

    def thread_rtcm_port_receiver(self, *args, **kwargs):
        if self.rtcm_logf is None:
            return
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.rtcm_serial_port.read_all())
            except Exception as e:
                print_red('RTCM PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if len(data):
                self.rtcm_logf.write(data)
            else:
                time.sleep(0.001)

    def before_write_content(self, core, content_len):
        self.communicator.serial_port.baudrate = self.bootloader_baudrate
        self.communicator.serial_port.reset_input_buffer()

        message_bytes = [ord('C'), ord(core)]
        message_bytes.extend(struct.pack('>I', content_len))
        command_line = helper.build_packet('CS', message_bytes)
        for i in range(5):
            self.communicator.write(command_line, True)
            time.sleep(1)
            result = helper.read_untils_have_data(
                self.communicator, 'CS', 200, 100)
            if result:
                break

        if not result:
            raise Exception('Cannot run set core command')

    def firmware_write_command_generator(self, data_len, current, data):
        command_WA = 'WA'
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('B', data_len))
        message_bytes.extend(data)
        return helper.build_packet(command_WA, message_bytes)

    # override
    def build_worker(self, rule, content):
        if rule == 'rtk':
            rtk_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
                lambda: helper.format_firmware_content(content),
                self.firmware_write_command_generator,
                192)
            rtk_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(15))
            rtk_upgrade_worker.on(UPGRADE_EVENT.BEFORE_WRITE,
                                  lambda: self.before_write_content('0', len(content)))
            return rtk_upgrade_worker

        if rule == 'ins':
            ins_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
                lambda: helper.format_firmware_content(content),
                self.firmware_write_command_generator,
                192)
            ins_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(15))
            ins_upgrade_worker.on(UPGRADE_EVENT.BEFORE_WRITE,
                                  lambda: self.before_write_content('1', len(content)))
            return ins_upgrade_worker

        if rule == 'sdk':
            sdk_upgrade_worker = SDK9100UpgradeWorker(
                self.communicator, self.bootloader_baudrate, content)
            return sdk_upgrade_worker

    # command list
    # use base methods


class beidouProvider(beidouProviderBase):
    '''
    beidou UART provider
    '''

    def __init__(self, communicator, *args):
        try:
            super(beidouProvider, self).__init__(communicator)
        except Exception as e:
            print(e)
        self.type = 'beidou'
        self.bootloader_baudrate = 115200
        self.config_file_name = 'beidou.json'
        self.device_category = 'beidou'
        self.port_index_define = {
            'user': 0,
            'rtcm': 3,
            'debug': 2,
        }

    def thread_debug_port_receiver(self, *args, **kwargs):
        if self.debug_logf is None:
            return

        # log data
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.debug_serial_port.read_all())
            except Exception as e:
                print_red('DEBUG PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if data and len(data) > 0:
                self.debug_logf.write(data)
            else:
                time.sleep(0.001)

    def thread_rtcm_port_receiver(self, *args, **kwargs):
        if self.rtcm_logf is None:
            return
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.rtcm_serial_port.read_all())
            except Exception as e:
                print_red('RTCM PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if len(data):
                self.rtcm_logf.write(data)
            else:
                time.sleep(0.001)

    def before_write_content(self, core, content_len):
        self.communicator.serial_port.baudrate = self.bootloader_baudrate
        self.communicator.serial_port.reset_input_buffer()

        message_bytes = [ord('C'), ord(core)]
        message_bytes.extend(struct.pack('>I', content_len))
        command_line = helper.build_packet('CS', message_bytes)
        for i in range(5):
            self.communicator.write(command_line, True)
            time.sleep(1)
            result = helper.read_untils_have_data(
                self.communicator, 'CS', 200, 100)
            if result:
                break

        if not result:
            raise Exception('Cannot run set core command')

    def firmware_write_command_generator(self, data_len, current, data):
        command_WA = 'WA'
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('B', data_len))
        message_bytes.extend(data)
        return helper.build_packet(command_WA, message_bytes)

    # override
    def build_worker(self, rule, content):

        if rule == 'ins':
            ins_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
                True,
                lambda: helper.format_firmware_content(content),
                self.firmware_write_command_generator,
                192)
            ins_upgrade_worker.name = 'INS'
            ins_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(15))
            ins_upgrade_worker.on(UPGRADE_EVENT.BEFORE_WRITE,
                                  lambda: self.before_write_content('1', len(content)))
            return ins_upgrade_worker

        
        if rule == 'imu':
            imu_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
				True,
                lambda: helper.format_firmware_content(content),
                self.firmware_write_command_generator,
                192)
            imu_upgrade_worker.name = 'IMU'
            imu_upgrade_worker.group = UPGRADE_GROUP.FIRMWARE
            imu_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(20))
            return imu_upgrade_worker
