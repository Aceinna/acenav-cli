import math
import re
import sys
import time
import os
import signal
import struct

try:
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils.print import (print_green, print_red)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins402 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
except:  # pylint: disable=bare-except
    print('load package from local')
    sys.path.append('./src')
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils.print import (print_green, print_red)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins402 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES

FILE_NAME = './toro_rlx.bin'

class FileContent:
    content: bytes = None
    content_size: int = 0
    block_size: int = 1024
    block_number: int = 0

    def __init__(self, file_path) -> None:
        self.content = self.read_file(file_path)
        self.content_size = len(self.content)
        self.block_number = math.ceil(self.content_size / self.block_size)

    def read_file(self, file_path):
        with open(file_path, 'rb') as file:
            return file.read()

def test_fail_configuration_algorithm_command(configuration: FileContent, device_provider: EhternetProvider):
    result = device_provider.configure_do_send_packet(
        configuration.content, configuration.block_size)
    if not result:
        print_green('send packet command before prepare command. Should be failed: Yes')
    else:
        print_red('send packet command before prepare command. Should be failed: No')
        return False

    wrong_block_size = 512
    device_provider.configure_do_send_prepare(
        configuration.content_size, configuration.block_number)
    result = device_provider.configure_do_send_packet(
        configuration.content, wrong_block_size)
    if not result:
        print_green('send packet command in wrong size. Should be failed: Yes')
    else:
        print_red('send packet command in wrong size. Should be failed: No')
        return False

def test_configuration_algorithm_command(configuration: FileContent, device_provider: EhternetProvider):
    # test send prepare command
    result = device_provider.configure_do_send_prepare(
        configuration.content_size, configuration.block_number)
    if result:
        print_green('send prepare command ok.')
    else:
        print_red('send prepare command error.')
        return False

    # test send packet command
    result = device_provider.configure_do_send_packet(
        configuration.content, configuration.block_size)
    if result:
        print_green('send packet command ok.')
    else:
        print_red('send packet command error.')
        return False

    # test reset command
    result = device_provider.configure_do_reset()
    if result:
        print_green('device reset and ping ok.')
    else:
        print_red('device reset and ping error.')
        return False

    return True

def test_configuration_algorithm_process(device_provider: EhternetProvider):
    cmd_str = 'configure {0}'.format(FILE_NAME)
    cmd_list = re.split(r'\s+', cmd_str)

    return device_provider.configure_algorithm(cmd_list)

def handle_discovered(device_provider):
    configuration = FileContent(FILE_NAME)

    result = test_fail_configuration_algorithm_command(configuration, device_provider)
    if result:
        print_green('test fail config algorithm command ok.')
    else:
        print_red('test fail config algorithm command error.')
        return

    result = test_configuration_algorithm_command(
        configuration, device_provider)
    if result:
        print_green('test config algorithm command ok.')
    else:
        print_red('test config algorithm command error.')
        return

    result = test_configuration_algorithm_process(device_provider)
    if result:
        print_green('test config algorithm process ok.')
    else:
        print_red('test config algorithm process error.')
        return


def kill_app(signal_int, call_back):
    '''Kill main thread
    '''
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit()


@handle_application_exception
def simple_start():
    driver = Driver(WebserverArgs(
        interface=INTERFACES.ETH_100BASE_T1,
        device_type='INS402',
        use_cli=True
    ))
    driver.on(DriverEvents.Discovered, handle_discovered)
    driver.detect()


if __name__ == '__main__':
    simple_start()

    while True:
        signal.signal(signal.SIGINT, kill_app)
