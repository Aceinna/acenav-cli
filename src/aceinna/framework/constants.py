# Device
DEVICE_TYPES = ['RTK', 'beidou', 'INS402', 'INS502']
BAUDRATE_LIST = [460800, 115200, 57600, 230400, 38400]
DEFAULT_PORT_RANGE = [8000, 8001, 8002, 8003]


class APP_TYPE:
    DEFAULT = 'default'
    CLI = 'cli'
    RECEIVER = 'receiver'
    LOG_PARSER = 'log-parser'
    CANFD = 'canfd'


class INTERFACES(object):
    UART = 'uart'
    ETH_100BASE_T1 = '100base-t1'
    BOARD = 'beidou'
    CANFD = 'canfd'
    def list():
        return [INTERFACES.UART, INTERFACES.ETH_100BASE_T1, INTERFACES.CANFD]
