from array import array
import time
import os

from ..base.upgrade_worker_base import UpgradeWorkerBase
from ...framework.utils import helper
from ...framework.command import Command
from . import (UPGRADE_EVENT, UPGRADE_GROUP)

IMU_JI_CMD = [0x4a, 0x49]

class JumpBootloaderWorker(UpgradeWorkerBase):
    '''Firmware upgrade worker
    '''
    _command = None
    _listen_packet = None
    _wait_timeout_after_command = 3

    def __init__(self, communicator, ack_enable, *args, **kwargs):
        super(JumpBootloaderWorker, self).__init__()
        self._communicator = communicator
        self.ack_enable = ack_enable
        self.current = 0
        self.total = 0
        self._group = UPGRADE_GROUP.FIRMWARE

        if kwargs.get('command'):
            self._command = kwargs.get('command')

        if kwargs.get('listen_packet'):
            self._listen_packet = kwargs.get('listen_packet')

        if kwargs.get('wait_timeout_after_command'):
            self._wait_timeout_after_command = kwargs.get(
                'wait_timeout_after_command')
        
        if kwargs.get('ethernet_reshake'):
            self._ethernet_reshake = kwargs.get('ethernet_reshake')

        if kwargs.get('system_reset'):
            self._system_reset = kwargs.get('system_reset')
        
    def stop(self):
        self._is_stopped = True

    def get_upgrade_content_size(self):
        return self.total
            
    def imu_jump_iap_command(self, actual_command, payload_length_format):
        response = None
        retry_cnt = int((self._wait_timeout_after_command+4)/5)

        for i in range(retry_cnt):
            for i in range(5):
                self._communicator.write(actual_command)
                time.sleep(0.5)
                response = helper.read_untils_have_data(
                            self._communicator, self._listen_packet, 100, 500, payload_length_format)
                if response is not None:
                    break

            if response is None:
                if self._system_reset and callable(self._system_reset):
                    self._system_reset()

                if self._ethernet_reshake and callable(self._ethernet_reshake):
                    self._ethernet_reshake()
            else:
                break

        return response

    def work(self):
        '''Send JI command
        '''
        if self._is_stopped:
            return

        if self._command:
            actual_command = None
            payload_length_format = 'B'

            if callable(self._command):
                self._command = self._command()

            if  isinstance(self._command, Command):
                actual_command = self._command.actual_command
                payload_length_format = self._command.payload_length_format

            if isinstance(self._command, list):
                actual_command = self._command

            self.emit(UPGRADE_EVENT.BEFORE_COMMAND)
            self._communicator.reset_buffer()
            
            if self.ack_enable:
                if self._listen_packet == IMU_JI_CMD:
                    response = self.imu_jump_iap_command(actual_command, payload_length_format)
                else:
                    for i in range(self._wait_timeout_after_command):
                        self._communicator.write(actual_command)
                        time.sleep(0.5)
                        response = helper.read_untils_have_data(
                                    self._communicator, self._listen_packet, 100, 1000, payload_length_format)
                        if response is not None:
                            break
                
                if(response is None):
                    self.emit(UPGRADE_EVENT.ERROR, self._key,
                        'jump bootloader fail')
                    print('jump bootloader fail, {0}'.format(self._key))
                    os._exit(1)
            else:
                self._communicator.write(actual_command)
                time.sleep(10)

            self.emit(UPGRADE_EVENT.AFTER_COMMAND)

        self.emit(UPGRADE_EVENT.FINISH, self._key)
