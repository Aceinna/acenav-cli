import sys
import time
import os
import signal
import struct
import threading
import datetime
import re

try:
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins402 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
except:  # pylint: disable=bare-except
    print('load package from local')
    sys.path.append('./src')
    from aceinna.core.driver import (Driver, DriverEvents)
    from aceinna.models.args import WebserverArgs
    from aceinna.framework.utils import (helper)
    from aceinna.framework.decorator import handle_application_exception
    from aceinna.devices.ins401.ethernet_provider_ins402 import Provider as EhternetProvider
    from aceinna.framework.constants import INTERFACES
    
setattr(sys, '__dev__', True)

# loop firmware upgrade and log
def loop_upgrade(EhternetProvider):
    loop_upgrade_cnt = 0
    
    upgrade_log_file = open(r'.\upgrade_log.txt', 'w+')

    # 'upgrade ./INS402_31.00.01_test.bin sdk imu' 
    # 'upgrade ./INS402_31.00.01_test.bin rtk ins' 
    # 'upgrade ./INS402_31.00.01_test.bin rtk ins sdk imu' 
    # 'upgrade ./INS402_31.00.01_test.bin'
    upgrade_cmd_str = 'upgrade ./INS402_31.00.01_test.bin rtk ins'

    upgrade_cmd_list = re.split(r'\s+', upgrade_cmd_str)

    while True:
        if EhternetProvider.loop_upgrade_flag:
            time.sleep(1)
            continue

        if EhternetProvider.is_upgrading == False:
            time.sleep(1)
            loop_upgrade_cnt += 1
            print('\nloop_upgrade_cnt: %d\n' % loop_upgrade_cnt)
            print(upgrade_cmd_str)
            
            print('\nloop_upgrade_cnt: %d\n' % loop_upgrade_cnt, file = upgrade_log_file, flush = True)
            device_info = EhternetProvider._device_info_string.replace('\n', '')
            print('{0}\n'.format(device_info), file = upgrade_log_file, flush = True)
            print(upgrade_cmd_str, file = upgrade_log_file, flush = True)
            print("Upgrade INS401 firmware started at:[{0}].".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), file = upgrade_log_file, flush = True)

        EhternetProvider.upgrade_framework(upgrade_cmd_list)

        if loop_upgrade_cnt == 500:
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
        if (EhternetProvider.is_upgrading == False)\
            and EhternetProvider.loop_upgrade_flag == False:
            if loop_upgrade_thread:
                loop_upgrade_thread.join(0.5)
        else:
            if ntrip_client_thread:
                ntrip_client_thread.join(0.5)
    

def kill_app(signal_int, call_back):
    '''Kill main thread
    '''
    os.kill(os.getpid(), signal.SIGTERM)
    sys.exit()

@handle_application_exception
def simple_start(): 
    driver = Driver(WebserverArgs(
        interface = INTERFACES.ETH_100BASE_T1,
        device_type = 'INS402',
        use_cli = True
    ))
    driver.on(DriverEvents.Discovered, handle_discovered)
    driver.detect()


if __name__ == '__main__':
    simple_start()

    while  True:
        signal.signal(signal.SIGINT, kill_app)




