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
    from aceinna.devices.ins401.ethernet_provider_ins401 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
except:  # pylint: disable=bare-except
    print('load package from local')
    sys.path.append('./src')
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins401 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES

# Only loop firmware upgrade 
# def handle_discovered(device_provider):
#     loop_upgrade_cnt = 0

#     upgrade_log_file = open(r'.\upgrade_log.txt', 'w+')

#     while True:
#         if device_provider.is_upgrading == False:     
#             loop_upgrade_cnt += 1
#             print('loop_upgrade_cnt: %d' % loop_upgrade_cnt)
#             print('loop_upgrade_cnt: %d' % loop_upgrade_cnt, file = upgrade_log_file, flush = True)

#         device_provider.upgrade_framework(['upgrade', './INS401_28.03a.bin'])
#         if loop_upgrade_cnt == 200:
#             os._exit(1)

#         time.sleep(5)

# loop firmware upgrade and log
def loop_upgrade(EhternetProvider):
    loop_upgrade_cnt = 0
    
    upgrade_log_file = open(r'.\upgrade_log.txt', 'w+')

    while True:
        if EhternetProvider.is_upgrading == False:
            time.sleep(10)
            loop_upgrade_cnt += 1
            print('loop_upgrade_cnt: %d' % loop_upgrade_cnt)
            print('loop_upgrade_cnt: %d' % loop_upgrade_cnt, file = upgrade_log_file, flush = True)
            
        EhternetProvider.upgrade_framework(['upgrade', './INS401_v28.04.20.bin'])

        if loop_upgrade_cnt == 300:
            os._exit(1)

        time.sleep(5)

def handle_discovered(EhternetProvider):
    ntrip_client_thread = None
    loop_upgrade_thread = None

    loop_upgrade_thread = threading.Thread(target=loop_upgrade, args = (EhternetProvider,))
    ntrip_client_thread = threading.Thread(target=EhternetProvider.ntrip_client_thread)
    loop_upgrade_thread.start()
    ntrip_client_thread.start()

    while True:
        if EhternetProvider.is_upgrading == False:
            if loop_upgrade_thread:
                loop_upgrade_thread.join(1.0)
        else:
            if ntrip_client_thread:
                ntrip_client_thread.join(1.0)
    

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




