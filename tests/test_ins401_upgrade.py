import sys
import time
import os
import signal
import struct
import threading

try:
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
except:  # pylint: disable=bare-except
    print('load package from local')
    sys.path.append('./src')
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES

def handle_discovered(device_provider):
    loop_upgrade_cnt = 0

    while True:
        if device_provider.is_upgrading == False:     
            loop_upgrade_cnt += 1
            print("loop_upgrade_cnt:", loop_upgrade_cnt)
        device_provider.upgrade_framework("./INS401_28.02a.bin")

        time.sleep(5)


    pass

def kill_app(signal_int, call_back):
    '''Kill main thread
    '''
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit()

@handle_application_exception
def simple_start():
    driver = Driver(WebserverArgs(
        interface = INTERFACES.ETH_100BASE_T1,
        use_cli = True
    ))
    driver.on(DriverEvents.Discovered, handle_discovered)
    driver.detect()


if __name__ == '__main__':
    simple_start()

    while  True:
        signal.signal(signal.SIGINT, kill_app)




