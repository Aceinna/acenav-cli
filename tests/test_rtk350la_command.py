import sys
import time
import os
import signal
import struct

try:
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins401 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
except:  # pylint: disable=bare-except
    print('load package from local')
    sys.path.append('./src')
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.rtk350la.uart_provider import Provider as UartProvider
    from aceinna.framework.constants import INTERFACES

def set_user_configuration(command, message_bytes):

    command_line = helper.build_packet(command, message_bytes)
    return command_line

def get_user_configuration_parameters(command, field_id):
    message_bytes = []

    field_id_bytes = struct.pack('<I', field_id)
    message_bytes.extend(field_id_bytes)

    command_line = helper.build_packet(command, message_bytes)
    return command_line

def get_production_info(dest, src, command):
    message_bytes = []

    command_line = helper.build_packet(dest, src, command, message_bytes)
    return command_line


def rtk350la_configuration_command_send_receive(device_provider):
    global data
    def on_resolve(*args, **kwargs):
        global data
        data =  {
            'packet_type': kwargs['packet_type'],
            'data': kwargs['data'],
            'error': kwargs['error'],
            'raw': kwargs['raw']
        }
        print(data, data['error'])
    user_parameters = [2, 1, 100]
    for i in range(0, len(user_parameters), 3):
        command_line = set_user_configuration('uB', user_parameters[i:i+3])
        # for ele in command_line:
        #     print("%02x" % ele)
        # print('command_line: ', command_line)
        if command_line:
            device_message = device_provider._message_center.build(command_line)
            device_message.on('finished', on_resolve)
            device_message.send()
            time.sleep(1)
            result = data['error']
            print('get_user_configuration_parameters:', result)
            return result
        else:
            return False

def handle_discovered(device_provider):
    result = rtk350la_configuration_command_send_receive(device_provider)
    if result:
        print('rtk350la command test ok.')
    else:
        print('rtk350la command test error.')

def kill_app(signal_int, call_back):
    '''Kill main thread
    '''
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit()

@handle_application_exception
def simple_start():
    driver = Driver(WebserverArgs(
        interface=INTERFACES.UART,
        use_cli = True
    ))
    driver.on(DriverEvents.Discovered, handle_discovered)
    driver.detect()


if __name__ == '__main__':
    simple_start()

    while  True:
        signal.signal(signal.SIGINT, kill_app)




