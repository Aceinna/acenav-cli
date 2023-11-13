from .rtk330l import ping as ping_rtk330l
from .ins import ping as ping_ins
from .beidou import ping as ping_beidou
from .open import ping as ping_opendevice
from ...framework.context import APP_CONTEXT
from ...framework.constants import INTERFACES

def do_ping(communicator_type, device_access, filter_device_type):
    if communicator_type == INTERFACES.UART:
        # if filter_device_type is None or filter_device_type in ['RTKL', 'beidou']:
        if filter_device_type in ['RTKL', 'beidou']:
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

        elif filter_device_type is None:
            ping_result = ping_opendevice(
                device_access, filter_device_type)
            if ping_result:
                return ping_result

    if communicator_type == INTERFACES.ETH_100BASE_T1:
        if filter_device_type in ['INS401', 'INS402', 'INS502']:
            ping_tools = ping_ins
        else:
            filter_device_type = 'INS401'
            ping_tools = ping_ins

        APP_CONTEXT.get_logger().logger.debug('Checking if is {0} device...'.format(filter_device_type))

        if ping_tools:
            ping_result = ping_tools(device_access, filter_device_type)
            if ping_result:
                return ping_result

    return None
