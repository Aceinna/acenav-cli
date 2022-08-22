from .rtk330l import ping as ping_rtk330l
from .ins401 import ping as ping_ins401
from .ins402 import ping as ping_ins402
from .beidou import ping as ping_beidou
from ...framework.context import APP_CONTEXT
from ...framework.constants import INTERFACES

def do_ping(communicator_type, device_access, filter_device_type):
    if communicator_type == INTERFACES.UART:
        if filter_device_type is None or filter_device_type in ['RTKL', 'beidou']:
            APP_CONTEXT.get_logger().logger.debug(
                'Checking if is RTK330L device...')
            ping_result = ping_rtk330l(
                device_access, filter_device_type)
            if ping_result:
                return ping_result
            ping_result = ping_beidou(
                device_access, filter_device_type)
            if ping_result:
                return ping_result

    if communicator_type == INTERFACES.ETH_100BASE_T1:
        if device_access.filter_device_type == 'INS402':
            pin_tools = ping_ins402
        else:
            pin_tools = ping_ins401
        APP_CONTEXT.get_logger().logger.debug('Checking if is INS401 device...')
        ping_result = pin_tools(device_access, None)
        if ping_result:
            return ping_result

    return None
