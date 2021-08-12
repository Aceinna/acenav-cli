from .ins401 import ping as ping_ins401
from ...framework.context import APP_CONTEXT
from ...framework.constants import INTERFACES

def do_ping(communicator_type, device_access, filter_device_type):

    if communicator_type == INTERFACES.ETH_100BASE_T1:
        APP_CONTEXT.get_logger().logger.debug('Checking if is INS401 device...')
        ping_result = ping_ins401(device_access, None)
        if ping_result:
            return ping_result

    return None
