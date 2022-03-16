from .ping import ping_tool
from .rtkl.uart_provider import Provider as RTKLUartProvider
from .rtkl.uart_provider import beidouProvider as beidouUartProvider
from .ins401.ethernet_provider import Provider as INS401EthernetProvider
from ..framework.context import APP_CONTEXT
from ..framework.utils.print import print_green
from ..framework.constants import INTERFACES

def create_provider(device_type, communicator):
    if communicator.type == INTERFACES.UART:
        if device_type == 'RTKL':
            return RTKLUartProvider(communicator)
        elif device_type == 'beidou':
            return beidouUartProvider(communicator)
    if communicator.type==INTERFACES.ETH_100BASE_T1:
        if device_type == 'INS401':
            return INS401EthernetProvider(communicator)

    return None


class DeviceManager:
    '''
    Manage devices
    '''
    device_list = []

    @staticmethod
    def build_provider(communicator, device_access, ping_info):
        if ping_info is None:
            return None

        device_type = ping_info['device_type']
        device_info = ping_info['device_info']
        app_info = ping_info['app_info']

        provider = None
        # find provider from cached device_list
        for index in range(len(DeviceManager.device_list)):
            exist_device = DeviceManager.device_list[index]
            if exist_device['device_type'] == device_type and \
                    exist_device['communicator_type'] == communicator.type:
                provider = exist_device['provider']
                provider.communicator = communicator
                break

        if provider is None:
            provider = create_provider(device_type, communicator)
            if provider is None:
                return None

            DeviceManager.device_list.append({
                'device_type': device_type,
                'communicator_type': communicator.type,
                'provider': provider
            })
        else:
            communicator.upgrading_flag = False

        format_device_info = provider.bind_device_info(
            device_access, device_info, app_info)

        print_green(format_device_info)

        APP_CONTEXT.get_logger().logger.info(
            'Connected Device info {0}'.format(format_device_info))
        return provider

    @staticmethod
    def ping(communicator, *args):
        '''
            Find device with ping command
            uart: communicator, device_type
            lan: communicator
        '''
        if communicator.type == INTERFACES.UART:
            device_access = args[0]
            filter_device_type = args[1]

            ping_result = ping_tool.do_ping(
                communicator.type, device_access, filter_device_type)
            if ping_result is not None:
                return DeviceManager.build_provider(communicator, device_access, ping_result)
        if communicator.type == INTERFACES.ETH_100BASE_T1:
            device_access = args[0]
            
            ping_result = ping_tool.do_ping(communicator.type, device_access,
                                            None)
            if ping_result is not None:
                return DeviceManager.build_provider(communicator, device_access, ping_result)

        return None
