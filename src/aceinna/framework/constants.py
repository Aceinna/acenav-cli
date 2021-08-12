# Device
DEVICE_TYPES = ['IMU', 'RTK', 'DMU']
DEFAULT_PORT_RANGE = [8000, 8001, 8002, 8003]


class APP_TYPE:
    DEFAULT = 'default'
    CLI = 'cli'
    RECEIVER = 'receiver'
    LOG_PARSER = 'log-parser'


class INTERFACES(object):
    ETH_100BASE_T1 = '100base-t1'

    def list():
        return [INTERFACES.ETH_100BASE_T1]
