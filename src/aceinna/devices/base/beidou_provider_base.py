import os
import time
import json
import datetime
import threading
import math
import re
import collections
import serial
import serial.tools.list_ports
from ..widgets import NTRIPClient
from ..widgets import BTServer
from ...framework.utils import (
    helper, resource
)
from ...framework.context import APP_CONTEXT
from ...framework.utils.firmware_parser import parser as firmware_content_parser
from ...framework.utils.print import (print_green, print_yellow, print_red)
from ..base import OpenDeviceBase
from ..configs.beidou_predefine import (
    APP_STR, get_beidou_products, get_configuratin_file_mapping
)
from ..decorator import with_device_message
from ...models import InternalCombineAppParseRule
from ..upgrade_workers import (
    FirmwareUpgradeWorker,
    JumpApplicationWorker,
    JumpBootloaderWorker,
    UPGRADE_EVENT,
    UPGRADE_GROUP
)
from ..parsers.rtk330l_field_parser import encode_value
from abc import ABCMeta, abstractmethod
from ..ping.rtk330l import ping
from ..ping.beidou import ping as beidou_ping
import zlib

class beidouProviderBase(OpenDeviceBase):
    '''
    beidou Series UART provider
    '''
    __metaclass__ = ABCMeta

    def __init__(self, communicator, *args):
        super(beidouProviderBase, self).__init__(communicator)
        self.type = 'beidou'
        self.server_update_rate = 100
        self.sky_data = []
        self.pS_data = []
        self.ps_dic = collections.OrderedDict()
        self.inspva_flag = 0
        self.bootloader_baudrate = 115200
        self.app_config_folder = ''
        self.device_info = None
        self.app_info = None
        self.parameters = None
        self.setting_folder_path = None
        self.data_folder = None
        self.debug_serial_port = None
        self.rtcm_serial_port = None
        self.user_logf = None
        self.debug_logf = None
        self.rtcm_logf = None
        self.debug_c_f = None
        self.ntrip_rtcm_logf = None
        self.enable_data_log = False
        self.is_app_matched = False
        self.ntrip_client_enable = False
        self.nmea_buffer = []
        self.nmea_sync = 0
        self.config_file_name = 'openrtk.json'
        self.device_category = 'beidou'
        self.prepare_folders()
        self.ntrip_client = None
        self.beidou_log_file_name = ''
        self.connected = False
        self.port_index_define = {
            'user': 0,
            'rtcm': 1,
            'debug': 2,
        }
        self.device_message = None
        self.crc32Table =\
        [
            0x00000000, 0x77073096, 0xee0e612c, 0x990951ba, 0x076dc419,0x706af48f,
            0xe963a535, 0x9e6495a3, 0x0edb8832, 0x79dcb8a4, 0xe0d5e91e,0x97d2d988,
            0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91, 0x1db71064,0x6ab020f2,
            0xf3b97148, 0x84be41de, 0x1adad47d, 0x6ddde4eb, 0xf4d4b551,0x83d385c7,
            0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec, 0x14015c4f,0x63066cd9,
            0xfa0f3d63, 0x8d080df5, 0x3b6e20c8, 0x4c69105e, 0xd56041e4,0xa2677172,
            0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b, 0x35b5a8fa,0x42b2986c,
            0xdbbbc9d6, 0xacbcf940, 0x32d86ce3, 0x45df5c75, 0xdcd60dcf,0xabd13d59,
            0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116, 0x21b4f4b5,0x56b3c423,
            0xcfba9599, 0xb8bda50f, 0x2802b89e, 0x5f058808, 0xc60cd9b2,0xb10be924,
            0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d, 0x76dc4190,0x01db7106,
            0x98d220bc, 0xefd5102a, 0x71b18589, 0x06b6b51f, 0x9fbfe4a5,0xe8b8d433,
            0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818, 0x7f6a0dbb,0x086d3d2d,
            0x91646c97, 0xe6635c01, 0x6b6b51f4, 0x1c6c6162, 0x856530d8,0xf262004e,
            0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457, 0x65b0d9c6,0x12b7e950,
            0x8bbeb8ea, 0xfcb9887c, 0x62dd1ddf, 0x15da2d49, 0x8cd37cf3,0xfbd44c65,
            0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2, 0x4adfa541,0x3dd895d7,
            0xa4d1c46d, 0xd3d6f4fb, 0x4369e96a, 0x346ed9fc, 0xad678846,0xda60b8d0,
            0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9, 0x5005713c,0x270241aa,
            0xbe0b1010, 0xc90c2086, 0x5768b525, 0x206f85b3, 0xb966d409,0xce61e49f,
            0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4, 0x59b33d17,0x2eb40d81,
            0xb7bd5c3b, 0xc0ba6cad, 0xedb88320, 0x9abfb3b6, 0x03b6e20c,0x74b1d29a,
            0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683, 0xe3630b12,0x94643b84,
            0x0d6d6a3e, 0x7a6a5aa8, 0xe40ecf0b, 0x9309ff9d, 0x0a00ae27,0x7d079eb1,
            0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe, 0xf762575d,0x806567cb,
            0x196c3671, 0x6e6b06e7, 0xfed41b76, 0x89d32be0, 0x10da7a5a,0x67dd4acc,
            0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5, 0xd6d6a3e8,0xa1d1937e,
            0x38d8c2c4, 0x4fdff252, 0xd1bb67f1, 0xa6bc5767, 0x3fb506dd,0x48b2364b,
            0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60, 0xdf60efc3,0xa867df55,
            0x316e8eef, 0x4669be79, 0xcb61b38c, 0xbc66831a, 0x256fd2a0,0x5268e236,
            0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f, 0xc5ba3bbe,0xb2bd0b28,
            0x2bb45a92, 0x5cb36a04, 0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b,0x5bdeae1d,
            0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a, 0x9c0906a9,0xeb0e363f,
            0x72076785, 0x05005713, 0x95bf4a82, 0xe2b87a14, 0x7bb12bae,0x0cb61b38,
            0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21, 0x86d3d2d4,0xf1d4e242,
            0x68ddb3f8, 0x1fda836e, 0x81be16cd, 0xf6b9265b, 0x6fb077e1,0x18b74777,
            0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c, 0x8f659eff,0xf862ae69,
            0x616bffd3, 0x166ccf45, 0xa00ae278, 0xd70dd2ee, 0x4e048354,0x3903b3c2,
            0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db, 0xaed16a4a,0xd9d65adc,
            0x40df0b66, 0x37d83bf0, 0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f,0x30b5ffe9,
            0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6, 0xbad03605,0xcdd70693,
            0x54de5729, 0x23d967bf, 0xb3667a2e, 0xc4614ab8, 0x5d681b02,0x2a6f2b94,
            0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d
        ]
    def prepare_folders(self):
        '''
        Prepare folders for data storage and configuration
        '''

        executor_path = resource.get_executor_path()
        setting_folder_name = 'setting'

        data_folder_path = os.path.join(executor_path, 'data')
        if not os.path.isdir(data_folder_path):
            os.makedirs(data_folder_path)
        self.data_folder = data_folder_path

        # copy contents of app_config under executor path
        self.setting_folder_path = os.path.join(
            executor_path, setting_folder_name)

        all_products = get_beidou_products()
        config_file_mapping = get_configuratin_file_mapping()

        for product in all_products:
            product_folder = os.path.join(self.setting_folder_path, product)
            if not os.path.isdir(product_folder):
                os.makedirs(product_folder)

            for app_name in all_products[product]:
                app_name_path = os.path.join(product_folder, app_name)
                app_name_config_path = os.path.join(
                    app_name_path, config_file_mapping[product])

                if not os.path.isfile(app_name_config_path):
                    if not os.path.isdir(app_name_path):
                        os.makedirs(app_name_path)
                    app_config_content = resource.get_content_from_bundle(
                        setting_folder_name,
                        os.path.join(product,
                                     app_name,
                                     config_file_mapping[product]))
                    if app_config_content is None:
                        continue

                    with open(app_name_config_path, "wb") as code:
                        code.write(app_config_content)

    @property
    def is_in_bootloader(self):
        ''' Check if the connected device is in bootloader mode
        '''
        if not self.app_info or not self.app_info.__contains__('version'):
            return False

        version = self.app_info['version']
        version_splits = version.split(',')
        if len(version_splits) == 1:
            if 'bootloader' in version_splits[0].lower():
                return True

        return False

    def bind_device_info(self, device_access, device_info, app_info):
        self._build_device_info(device_info)
        self._build_app_info(app_info)
        self.connected = True

        port_name = device_access.port
        try:
            str_split = device_info.split()
            str_split.pop(3)
            device_info = ' '.join(str_split)
        except Exception as e:
            print(e)
        self._device_info_string = '# Connected {0} with UART on {1} #\nDevice: {2} \nFirmware: {3}'\
            .format(self.device_category, port_name, device_info, app_info)

        return self._device_info_string

    def _build_device_info(self, text):
        '''
        Build device info
        '''
        split_text = [x for x in text.split(' ') if x != '']
        sn = split_text[4]
        # remove the prefix of SN
        if sn.find('SN:') == 0:
            sn = sn[3:]

        self.device_info = {
            'name': split_text[0],
            'imu': split_text[1],
            'pn': split_text[2],
            'firmware_version': split_text[3],
            'sn': sn
        }

    def _build_app_info(self, text):
        '''
        Build app info
        '''
        app_version = text

        split_text = app_version.split(' ')
        app_name = next(
            (item for item in APP_STR if item in split_text), None)

        if not app_name:
            app_name = 'INS'
            self.is_app_matched = False
        else:
            self.is_app_matched = True

        self.app_info = {
            'app_name': app_name,
            'version': text
        }

    def load_properties(self):
        product_name = self.device_info['name']
        app_name = self.app_info['app_name']

        # Load config from user working path
        local_config_file_path = os.path.join(
            os.getcwd(), self.config_file_name)
        if os.path.isfile(local_config_file_path):
            with open(local_config_file_path) as json_data:
                self.properties = json.load(json_data)
                return

        # Load the openimu.json based on its app
        app_file_path = os.path.join(
            self.setting_folder_path, product_name, app_name, self.config_file_name)

        if not self.is_app_matched:
            print_yellow(
                'Failed to extract app version information from unit.' +
                '\nThe supported application list is {0}.'.format(APP_STR) +
                '\nTo keep runing, use INS configuration as default.' +
                '\nYou can choose to place your json file under execution path if it is an unknown application.')

        with open(app_file_path) as json_data:
            self.properties = json.load(json_data)

    def ntrip_client_thread(self):
        # print('new ntrip client')
        self.ntrip_client = NTRIPClient(self.properties)
        self.ntrip_client.on('parsed', self.handle_rtcm_data_parsed)
        if self.device_info.__contains__('sn') and self.device_info.__contains__('pn'):
            self.ntrip_client.set_connect_headers({
                'Ntrip-Sn': self.device_info['sn'],
                'Ntrip-Pn': self.device_info['pn']
            })
        self.ntrip_client.run()

    def bt_server_thread(self):
        self.bt_server = BTServer(self.device_message)
        self.bt_server.on('parsed', self.handle_rtcm_data_parsed)
        if self.device_info.__contains__('sn') and self.device_info.__contains__('pn'):
            self.bt_server.set_connect_headers({
                'Ntrip-Sn': self.device_info['sn'],
                'Ntrip-Pn': self.device_info['pn']
            })
        self.bt_server.run()


    def handle_rtcm_data_parsed(self, data):
        bytes_data = bytearray(data)
        if self.communicator.can_write() and not self.is_upgrading:
            self.communicator.write(bytes_data)

        self.ntrip_rtcm_logf.write(bytes_data)

    def build_connected_serial_port_info(self):
        if not self.communicator.serial_port:
            return None, None

        user_port = self.communicator.serial_port.port
        user_port_num = ''
        port_name = ''
        for i in range(len(user_port)-1, -1, -1):
            if (user_port[i] >= '0' and user_port[i] <= '9'):
                user_port_num = user_port[i] + user_port_num
            else:
                port_name = user_port[:i+1]
                break
        return user_port_num, port_name

    def after_setup(self):
        local_time = time.localtime()
        formatted_dir_time = time.strftime("%Y%m%d_%H%M%S", local_time)
        formatted_file_time = time.strftime("%Y_%m_%d_%H_%M_%S", local_time)
        debug_port = ''
        rtcm_port = ''
        set_user_para = self.cli_options and self.cli_options.set_user_para

        # save original baudrate
        if hasattr(self.communicator, 'serial_port'):
            self.original_baudrate = self.communicator.serial_port.baudrate

        if self.data_folder is None:
            raise Exception(
                'Data folder does not exists, please check if the application has create folder permission')

        try:
            self.beidou_log_file_name = os.path.join(
                self.data_folder, '{0}_log_{1}'.format(self.device_category.lower(), formatted_dir_time))
            os.mkdir(self.beidou_log_file_name)
        except:
            raise Exception(
                'Cannot create log folder, please check if the application has create folder permission')

        # set parameters from predefined parameters
        if set_user_para:
            result = self.set_params(
                self.properties["initial"]["userParameters"])
            if (result['packetType'] == 'success'):
                self.save_config()
            time.sleep(1)
            # check saved result
            result = self.check_predefined_result()
            self.save_device_info(result)
        else:
            self.save_device_info()

        self.set_log_type()
        # start ntrip client
        if self.properties["initial"].__contains__("ntrip") and not self.ntrip_client and not self.is_in_bootloader:
            self.ntrip_rtcm_logf = open(os.path.join(self.beidou_log_file_name, 'ntrip_rtcm_{0}.bin'.format(
                formatted_file_time)), "wb")

            thead = threading.Thread(target=self.ntrip_client_thread)
            thead.start()
            thread_bt = threading.Thread(target=self.bt_server_thread)
            thread_bt.start()

        try:
            if (self.properties["initial"]["useDefaultUart"]):
                user_port_num, port_name = self.build_connected_serial_port_info()
                if not user_port_num or not port_name:
                    return False
                debug_port = port_name + \
                    str(int(user_port_num) + self.port_index_define['debug'])
                rtcm_port = port_name + \
                    str(int(user_port_num) + self.port_index_define['rtcm'])
            else:
                for x in self.properties["initial"]["uart"]:
                    if x['enable'] == 1:
                        if x['name'] == 'DEBUG':
                            debug_port = x["value"]
                        elif x['name'] == 'GNSS':
                            rtcm_port = x["value"]

            self.user_logf = open(os.path.join(
                self.beidou_log_file_name, 'user_{0}.bin'.format(formatted_file_time)), "wb")

            if rtcm_port != '':
                print_green('{0} log GNSS UART {1}'.format(
                    self.device_category, rtcm_port))
                self.rtcm_serial_port = serial.Serial(
                    rtcm_port, '460800', timeout=0.1)
                if self.rtcm_serial_port.isOpen():
                    self.rtcm_logf = open(
                        os.path.join(self.beidou_log_file_name, 'rtcm_rover_{0}.bin'.format(
                            formatted_file_time)), "wb")
                    thead = threading.Thread(
                        target=self.thread_rtcm_port_receiver, args=(self.beidou_log_file_name,))
                    thead.start()

            if debug_port != '':
                print_green('{0} log DEBUG UART {1}'.format(
                    self.device_category, debug_port))
                self.debug_serial_port = serial.Serial(
                    debug_port, '460800', timeout=0.1)
                if self.debug_serial_port.isOpen():
                    self.debug_logf = open(
                        os.path.join(self.beidou_log_file_name, 'rtcm_base_{0}.bin'.format(
                            formatted_file_time)), "wb")
                    thead = threading.Thread(
                        target=self.thread_debug_port_receiver, args=(self.beidou_log_file_name,))
                    thead.start()

            # self.save_device_info()
        except Exception as ex:
            if self.debug_serial_port is not None:
                if self.debug_serial_port.isOpen():
                    self.debug_serial_port.close()
            if self.rtcm_serial_port is not None:
                if self.rtcm_serial_port.isOpen():
                    self.rtcm_serial_port.close()
            self.debug_serial_port = None
            self.rtcm_serial_port = None
            APP_CONTEXT.get_logger().logger.error(ex)
            print_red(
                'Can not log GNSS UART or DEBUG UART, pls check uart driver and connection!')
            return False

    def nmea_checksum(self, data):
        data = data.replace("\r", "").replace("\n", "").replace("$", "")
        nmeadata, cksum = re.split('\*', data)
        calc_cksum = 0
        for s in nmeadata:
            calc_cksum ^= ord(s)
        return int(cksum, 16), calc_cksum

    def CalcateCRC32(self, data):
        iIndex = 0
        crc32_value = 0
        for iIndex in range(len(data)):
            crc32_value = self.crc32Table[(crc32_value ^ ord(data[iIndex]) ) & 0xff] ^ (crc32_value >> 8)
        return crc32_value


    def unico_checkcrc(self, data):
        data = data.replace("\r", "").replace("\n", "").replace("#", "")
        nmeadata, crc32 = data.split('*')
        calc_crc32 = self.CalcateCRC32(nmeadata)
        return int(crc32, 16), calc_crc32

    def on_read_raw(self, data):
        for bytedata in data:
            if bytedata == 0x24 or bytedata == 0x23:
                self.nmea_buffer = []
                self.nmea_sync = 0
                self.nmea_buffer.append(chr(bytedata))
            else:
                self.nmea_buffer.append(chr(bytedata))
                if self.nmea_sync == 0:
                    if bytedata == 0x0D:
                        self.nmea_sync = 1
                elif self.nmea_sync == 1:
                    if bytedata == 0x0A:
                        try:
                            str_nmea = ''.join(self.nmea_buffer)
                            if str_nmea[0] == '$':
                                cksum, calc_cksum = self.nmea_checksum(
                                    str_nmea)
                            else:
                                cksum, calc_cksum = self.unico_checkcrc(
                                    str_nmea)
                            if cksum == calc_cksum:
                                if str_nmea.find("$GPGGA") != -1 or str_nmea.find("$GNGGA") != -1:
                                    if self.ntrip_client:
                                        self.ntrip_client.send(str_nmea)
                                    if self.bt_server:
                                        str_nmea_to_bt_list = str_nmea.replace('GNGGA', 'GPGGA').split('*')
                                        str_nmea_to_bt = str_nmea_to_bt_list[0].rsplit(',',1)[0] + ',*' + str_nmea_to_bt_list[1]
                                        print(str_nmea_to_bt)
                                        self.bt_server.send(str_nmea_to_bt)
                                    #self.add_output_packet('gga', str_nmea)
                                # print(str_nmea, end='')
                                APP_CONTEXT.get_print_logger().info(str_nmea.replace('\r\n', ''))
                                # else:
                                #     print("nmea checksum wrong {0} {1}".format(cksum, calc_cksum))
                                if self.cli_options.debug.lower() == 'true':
                                    if str_nmea.find("#HEADINGA") != -1 or str_nmea.find("$GPGGA") != -1 or str_nmea.find("$GNGGA") != -1:
                                        print(str_nmea)
                        except Exception as e:
                            # print('NMEA fault:{0}'.format(e))
                            pass
                    self.nmea_buffer = []
                    self.nmea_sync = 0

        if self.user_logf is not None:
            self.user_logf.write(data)

    @abstractmethod
    def thread_debug_port_receiver(self, *args, **kwargs):
        pass

    @abstractmethod
    def thread_rtcm_port_receiver(self, *args, **kwargs):
        pass

    def on_receive_output_packet(self, packet_type, data, *args, **kwargs):
        '''
        Listener for getting output packet
        '''
        # $GPGGA,080319.00,3130.4858508,N,12024.0998832,E,4,25,0.5,12.459,M,0.000,M,2.0,*46
        if packet_type == 'gN':
            if self.ntrip_client:
                # $GPGGA
                gpgga = '$GNGGA' #'$GPGGA'
                # time
                timeOfWeek = float(data['GPS_TimeofWeek']) - 18
                dsec = int(timeOfWeek)
                msec = timeOfWeek - dsec
                sec = dsec % 86400
                hour = int(sec / 3600)
                minute = int(sec % 3600 / 60)
                second = sec % 60
                gga_time = format(hour*10000 + minute*100 +
                                  second + msec, '09.2f')
                gpgga = gpgga + ',' + gga_time
                # latitude
                latitude = float(data['latitude']) * 180 / 2147483648.0
                if latitude >= 0:
                    latflag = 'N'
                else:
                    latflag = 'S'
                    latitude = math.fabs(latitude)
                lat_d = int(latitude)
                lat_m = (latitude-lat_d) * 60
                lat_dm = format(lat_d*100 + lat_m, '012.7f')
                gpgga = gpgga + ',' + lat_dm + ',' + latflag
                # longitude
                longitude = float(data['longitude']) * 180 / 2147483648.0
                if longitude >= 0:
                    lonflag = 'E'
                else:
                    lonflag = 'W'
                    longitude = math.fabs(longitude)
                lon_d = int(longitude)
                lon_m = (longitude-lon_d) * 60
                lon_dm = format(lon_d*100 + lon_m, '013.7f')
                gpgga = gpgga + ',' + lon_dm + ',' + lonflag
                # positionMode
                gpgga = gpgga + ',' + str(data['positionMode'])
                # svs
                gpgga = gpgga + ',' + str(data['numberOfSVs'])
                # hop
                gpgga = gpgga + ',' + format(float(data['hdop']), '03.1f')
                # height
                gpgga = gpgga + ',' + \
                    format(float(data['height']), '06.3f') + ',M'
                #
                gpgga = gpgga + ',0.000,M'
                # diffage
                gpgga = gpgga + ',' + \
                    format(float(data['diffage']), '03.1f') + ','
                # ckm
                checksum = 0
                for i in range(1, len(gpgga)):
                    checksum = checksum ^ ord(gpgga[i])
                str_checksum = hex(checksum)
                if str_checksum.startswith("0x"):
                    str_checksum = str_checksum[2:]
                gpgga = gpgga + '*' + str_checksum + '\r\n'
                APP_CONTEXT.get_print_logger().info(gpgga)
                print(gpgga)
                self.ntrip_client.send(gpgga)
                return

        elif packet_type == 'pS':
            try:
                if data['latitude'] != 0.0 and data['longitude'] != 0.0:
                    if self.pS_data:
                        if self.pS_data['GPS_Week'] == data['GPS_Week']:
                            if data['GPS_TimeofWeek'] - self.pS_data['GPS_TimeofWeek'] >= 0.2:
                                self.add_output_packet('pos', data)
                                self.pS_data = data

                                if data['insStatus'] >= 3 and data['insStatus'] <= 5:
                                    ins_status = 'INS_INACTIVE'
                                    if data['insStatus'] == 3:
                                        ins_status = 'INS_SOLUTION_GOOD'
                                    elif data['insStatus'] == 4:
                                        ins_status = 'INS_SOLUTION_FREE'
                                    elif data['insStatus'] == 5:
                                        ins_status = 'INS_ALIGNMENT_COMPLETE'

                                    ins_pos_type = 'INS_INVALID'
                                    if data['insPositionType'] == 1:
                                        ins_pos_type = 'INS_SPP'
                                    elif data['insPositionType'] == 4:
                                        ins_pos_type = 'INS_RTKFIXED'
                                    elif data['insPositionType'] == 5:
                                        ins_pos_type = 'INS_RTKFLOAT'

                                    inspva = '#INSPVA,%s,%10.2f, %s, %s,%12.8f,%13.8f,%8.3f,%9.3f,%9.3f,%9.3f,%9.3f,%9.3f,%9.3f' %\
                                        (data['GPS_Week'], data['GPS_TimeofWeek'], ins_status, ins_pos_type,
                                         data['latitude'], data['longitude'], data['height'],
                                         data['velocityNorth'], data['velocityEast'], data['velocityUp'],
                                         data['roll'], data['pitch'], data['heading'])
                                    APP_CONTEXT.get_print_logger().info(inspva)
                        else:
                            self.add_output_packet('pos', data)
                            self.pS_data = data
                    else:
                        self.add_output_packet('pos', data)
                        self.pS_data = data
            except Exception as e:
                pass

        elif packet_type == 'sK':
            if self.sky_data:
                if self.sky_data[0]['timeOfWeek'] == data[0]['timeOfWeek']:
                    self.sky_data.extend(data)
                else:
                    self.add_output_packet('skyview', self.sky_data)
                    self.add_output_packet('snr', self.sky_data)
                    self.sky_data = []
                    self.sky_data.extend(data)
            else:
                self.sky_data.extend(data)

        elif packet_type == 'g1':
            self.ps_dic['positionMode'] = data['position_type']
            self.ps_dic['numberOfSVs'] = data['number_of_satellites_in_solution']
            self.ps_dic['hdop'] = data['hdop']
            self.ps_dic['age'] = data['diffage']
            if self.inspva_flag == 0:
                self.ps_dic['GPS_Week'] = data['GPS_Week']
                self.ps_dic['GPS_TimeofWeek'] = data['GPS_TimeOfWeek'] * 0.001
                self.ps_dic['latitude'] = data['latitude']
                self.ps_dic['longitude'] = data['longitude']
                self.ps_dic['height'] = data['height']
                self.ps_dic['velocityMode'] = 1
                self.ps_dic['velocityNorth'] = data['north_vel']
                self.ps_dic['velocityEast'] = data['east_vel']
                self.ps_dic['velocityUp'] = data['up_vel']
                self.ps_dic['latitude_std'] = data['latitude_standard_deviation']
                self.ps_dic['longitude_std'] = data['longitude_standard_deviation']
                self.ps_dic['height_std'] = data['height_standard_deviation']
                self.ps_dic['north_vel_std'] = data['north_vel_standard_deviation']
                self.ps_dic['east_vel_std'] = data['east_vel_standard_deviation']
                self.ps_dic['up_vel_std'] = data['up_vel_standard_deviation']
                self.add_output_packet('pos', self.ps_dic)

        elif packet_type == 'i1':
            self.inspva_flag = 1
            if data['GPS_TimeOfWeek'] % 200 == 0:
                self.ps_dic['GPS_Week'] = data['GPS_Week']
                self.ps_dic['GPS_TimeofWeek'] = data['GPS_TimeOfWeek'] * 0.001
                self.ps_dic['latitude'] = data['latitude']
                self.ps_dic['longitude'] = data['longitude']
                self.ps_dic['height'] = data['height']
                if data['ins_position_type'] != 1 and data['ins_position_type'] != 4 and data['ins_position_type'] != 5:
                    self.ps_dic['velocityMode'] = 2
                else:
                    self.ps_dic['velocityMode'] = 1
                self.ps_dic['insStatus'] = data['ins_status']
                self.ps_dic['insPositionType'] = data['ins_position_type']
                self.ps_dic['velocityNorth'] = data['north_velocity']
                self.ps_dic['velocityEast'] = data['east_velocity']
                self.ps_dic['velocityUp'] = data['up_velocity']
                self.ps_dic['roll'] = data['roll']
                self.ps_dic['pitch'] = data['pitch']
                self.ps_dic['heading'] = data['heading']
                self.ps_dic['latitude_std'] = data['latitude_std']
                self.ps_dic['longitude_std'] = data['longitude_std']
                self.ps_dic['height_std'] = data['height_std']
                self.ps_dic['north_vel_std'] = data['north_velocity_std']
                self.ps_dic['east_vel_std'] = data['east_velocity_std']
                self.ps_dic['up_vel_std'] = data['up_velocity_std']
                self.ps_dic['roll_std'] = data['roll_std']
                self.ps_dic['pitch_std'] = data['pitch_std']
                self.ps_dic['heading_std'] = data['heading_std']
                self.add_output_packet('pos', self.ps_dic)

        elif packet_type == 'y1':
            if self.sky_data:
                if self.sky_data[0]['GPS_TimeOfWeek'] == data[0]['GPS_TimeOfWeek']:
                    self.sky_data.extend(data)
                else:
                    self.add_output_packet('skyview', self.sky_data)
                    self.add_output_packet('snr', self.sky_data)
                    self.sky_data = []
                    self.sky_data.extend(data)
            else:
                self.sky_data.extend(data)

        else:
            output_packet_config = next(
                (x for x in self.properties['userMessages']['outputPackets']
                 if x['name'] == packet_type), None)
            if output_packet_config and output_packet_config.__contains__('active') \
                    and output_packet_config['active']:
                timeOfWeek = int(data['GPS_TimeOfWeek']) % 60480000
                data['GPS_TimeOfWeek'] = timeOfWeek / 1000
                self.add_output_packet('imu', data)

    @abstractmethod
    def build_worker(self, rule, content):
        ''' Build upgarde worker by rule and content
        '''
        pass


    def after_jump_bootloader_command(self):
        pass


    def after_jump_app_command(self):
        # beidou ping device
        self.communicator.serial_port.baudrate = self.original_baudrate
        can_ping = False

        while not can_ping:
            self.communicator.reset_buffer()  # clear input and output buffer
            info = beidou_ping(self.communicator, None)
            # print('JA ping', info)
            if info:
                can_ping = True
            time.sleep(0.5)
        pass

    def get_upgrade_workers(self, firmware_content):
        workers = []
        rules = [
            InternalCombineAppParseRule('ins', 'ins_start:', 4),
        ]

        parsed_content = firmware_content_parser(firmware_content, rules)
        # foreach parsed content, if empty, skip register into upgrade center
        device_info = self.get_device_connection_info()
        for _, rule in enumerate(parsed_content):
            content = parsed_content[rule]
            if len(content) == 0:
                continue

            worker = self.build_worker(rule, content)
            if not worker:
                continue
            workers.append(worker)
        # prepare jump bootloader worker and jump application workder
        # append jump bootloader worker before the first firmware upgrade workder
        # append jump application worker after the last firmware uprade worker
        start_index = -1
        end_index = -1
        for i, worker in enumerate(workers):
            if isinstance(worker, FirmwareUpgradeWorker):
                start_index = i if start_index == -1 else start_index
                end_index = i

        jump_bootloader_command = helper.build_bootloader_input_packet(
            'JI')
        jumpBootloaderWorker = JumpBootloaderWorker(
            self.communicator,
            command=jump_bootloader_command,
            listen_packet='JI',
            wait_timeout_after_command=1)
        jumpBootloaderWorker.on(
            UPGRADE_EVENT.AFTER_COMMAND, self.after_jump_bootloader_command)

        jump_application_command = helper.build_bootloader_input_packet('JA')
        jumpApplicationWorker = JumpApplicationWorker(
            self.communicator,
            command=jump_application_command,
            listen_packet='JA',
            wait_timeout_after_command=1)
        jumpApplicationWorker.on(
            UPGRADE_EVENT.AFTER_COMMAND, self.after_jump_app_command)

        if start_index > -1 and end_index > -1:
            workers.insert(
                start_index, jumpBootloaderWorker)
            workers.insert(
                end_index+2, jumpApplicationWorker)
        return workers

    def get_device_connection_info(self):
        return {
            'modelName': self.device_info['name'],
            'deviceType': self.type,
            'serialNumber': self.device_info['sn'],
            'partNumber': self.device_info['pn'],
            'firmware': self.device_info['firmware_version']
        }

    def check_predefined_result(self):
        local_time = time.localtime()
        formatted_file_time = time.strftime("%Y_%m_%d_%H_%M_%S", local_time)
        file_path = os.path.join(
            self.beidou_log_file_name,
            'parameters_predefined_{0}.json'.format(formatted_file_time)
        )
        # save parameters to data log folder after predefined parameters setup
        result = self.get_params()
        if result['packetType'] == 'inputParams':
            with open(file_path, 'w') as outfile:
                json.dump(result['data'], outfile)
        #print(result)
        # compare saved parameters with predefined parameters
        hashed_predefined_parameters = helper.collection_to_dict(
            self.properties["initial"]["userParameters"], key='paramId')
        hashed_current_parameters = helper.collection_to_dict(
            result['data'], key='paramId')
        success_count = 0
        fail_count = 0
        fail_parameters = []
        for key in hashed_predefined_parameters:
            if hashed_current_parameters[key]['value'] == \
                    hashed_predefined_parameters[key]['value']:
                success_count += 1
            else:
                fail_count += 1
                fail_parameters.append(
                    hashed_predefined_parameters[key]['name'])

        check_result = 'Predefined Parameters are saved. Success ({0}), Fail ({1})'.format(
            success_count, fail_count)
        if success_count == len(hashed_predefined_parameters.keys()):
            print_green(check_result)

        if fail_count > 0:
            print_yellow(check_result)
            print_yellow('The failed parameters: {0}'.format(fail_parameters))
        return result
    def save_device_info(self, result=None):
        ''' Save device configuration
            File name: configuration.json
        '''
        if self.is_in_bootloader:
            return
        if result == None:
            result = self.get_params()

        device_configuration = None
        file_path = os.path.join(
            self.data_folder, self.beidou_log_file_name, 'configuration.json')

        if not os.path.exists(file_path):
            device_configuration = []
        else:
            with open(file_path) as json_data:
                device_configuration = (list)(json.load(json_data))

        if result['packetType'] == 'inputParams':
            session_info = dict()
            session_info['time'] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime())
            session_info['device'] = self.device_info
            session_info['app'] = self.app_info
            session_info['interface'] = self.cli_options.interface
            if session_info['interface'] == 'uart':
                session_info['path'] = self.communicator.serial_port.port
            parameters_configuration = dict()
            for item in result['data']:
                param_name = item['name']
                param_value = item['value']
                parameters_configuration[param_name] = param_value

            session_info['parameters'] = parameters_configuration
            device_configuration.append(session_info)
            self.device_message = json.dumps(parameters_configuration)
            with open(file_path, 'w') as outfile:
                json.dump(device_configuration, outfile,
                          indent=4, ensure_ascii=False)

    def after_upgrade_completed(self):
        self.communicator.reset_buffer()
        pass

    def get_operation_status(self):
        if self.is_logging:
            return 'LOGGING'

        return 'IDLE'

    # command list
    def server_status(self, *args):  # pylint: disable=invalid-name
        '''
        Get server connection status
        '''
        return {
            'packetType': 'ping',
            'data': {'status': '1'}
        }

    def get_device_info(self, *args):  # pylint: disable=invalid-name
        '''
        Get device information
        '''
        return {
            'packetType': 'deviceInfo',
            'data':  [
                {'name': 'Product Name', 'value': self.device_info['name']},
                {'name': 'IMU', 'value': self.device_info['imu']},
                {'name': 'PN', 'value': self.device_info['pn']},
                {'name': 'Firmware Version',
                 'value': self.device_info['firmware_version']},
                {'name': 'SN', 'value': self.device_info['sn']},
                {'name': 'App Version', 'value': self.app_info['version']}
            ]
        }

    def get_log_info(self):
        '''
        Build information for log
        '''
        return {
            "type": self.type,
            "model": self.device_info['name'],
            "logInfo": {
                "pn": self.device_info['pn'],
                "sn": self.device_info['sn'],
                "rtkProperties": json.dumps(self.properties)
            }
        }

    def get_conf(self, *args):  # pylint: disable=unused-argument
        '''
        Get json configuration
        '''
        return {
            'packetType': 'conf',
            'data': {
                'outputs': self.properties['userMessages']['outputPackets'],
                'inputParams': self.properties['userConfiguration']
            }
        }

    @with_device_message
    def get_params(self, *args):  # pylint: disable=unused-argument
        '''
        Get all parameters
        '''
        has_error = False
        parameter_values = []

        if self.app_info['app_name'] == 'INS':
            conf_parameters = self.properties['userConfiguration']
            conf_parameters_len = len(conf_parameters)-1
            step = 20
            for i in range(2, conf_parameters_len, step):
                start_byte = i
                end_byte = i+step-1 if i+step < conf_parameters_len else conf_parameters_len
                time.sleep(0.5)
                #print('xxxxxxxxxxxxxxxxxxxx',start_byte, end_byte)
                command_line = helper.build_packet(
                    'gB', [start_byte, end_byte])
                result = yield self._message_center.build(command=command_line, timeout=10)
                if result['error']:
                    has_error = True
                    break

                parameter_values.extend(result['data'])
        else:
            command_line = helper.build_input_packet('gA')
            result = yield self._message_center.build(command=command_line, timeout=3)
            if result['error']:
                has_error = True

            parameter_values = result['data']

        if not has_error:
            self.parameters = parameter_values
            yield {
                'packetType': 'inputParams',
                'data': parameter_values
            }

        yield {
            'packetType': 'error',
            'data': 'No Response'
        }

    @with_device_message
    def get_param(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramter value
        '''
        command_line = helper.build_input_packet(
            'gP', properties=self.properties, param=params['paramId'])
        # self.communicator.write(command_line)
        # result = self.get_input_result('gP', timeout=1)
        result = yield self._message_center.build(command=command_line)

        data = result['data']
        error = result['error']

        if error:
            yield {
                'packetType': 'error',
                'data': 'No Response'
            }

        if data:
            self.parameters = data
            yield {
                'packetType': 'inputParam',
                'data': data
            }

        yield {
            'packetType': 'error',
            'data': 'No Response'
        }

    @with_device_message
    def set_params(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramters value
        '''
        input_parameters = self.properties['userConfiguration']
        grouped_parameters = {}

        for parameter in params:
            exist_parameter = next(
                (x for x in input_parameters if x['paramId'] == parameter['paramId']), None)

            if exist_parameter:
                has_group = grouped_parameters.__contains__(
                    exist_parameter['category'])
                if not has_group:
                    grouped_parameters[exist_parameter['category']] = []

                current_group = grouped_parameters[exist_parameter['category']]

                current_group.append(
                    {'paramId': parameter['paramId'], 'value': parameter['value'], 'type': exist_parameter['type']})

        for group in grouped_parameters.values():
            message_bytes = []
            for parameter in group:
                message_bytes.extend(
                    encode_value('int8', parameter['paramId'])
                )
                message_bytes.extend(
                    encode_value(parameter['type'], parameter['value'])
                )
                # print('parameter type {0}, value {1}'.format(
                #     parameter['type'], parameter['value']))
            # result = self.set_param(parameter)
            command_line = helper.build_packet(
                'uB', message_bytes)
            # for s in command_line:
            #     print(hex(s))

            result = yield self._message_center.build(command=command_line)

            packet_type = result['packet_type']
            data = result['data']

            if packet_type == 'error':
                yield {
                    'packetType': 'error',
                    'data': {
                        'error': data
                    }
                }
                break

            if data > 0:
                yield {
                    'packetType': 'error',
                    'data': {
                        'error': data
                    }
                }
                break

        yield {
            'packetType': 'success',
            'data': {
                'error': 0
            }
        }

    #@with_device_message
    def set_log_type(self):  # pylint: disable=unused-argument
        log_cmd_list = self.properties['logCmd']
        command_line = bytes(''.join(log_cmd_list),encoding='utf-8')
        device_message = self._message_center.build(command=command_line)
        '''
        device_message.send()
        '''
        device_message._message_center._communicator.write(command_line)

    @with_device_message
    def set_param(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramter value
        '''
        command_line = helper.build_input_packet(
            'uP', properties=self.properties, param=params['paramId'], value=params['value'])
        # self.communicator.write(command_line)
        # result = self.get_input_result('uP', timeout=1)
        result = yield self._message_center.build(command=command_line)

        error = result['error']
        data = result['data']
        if error:
            yield {
                'packetType': 'error',
                'data': {
                    'error': data
                }
            }

        yield {
            'packetType': 'success',
            'data': {
                'error': data
            }
        }

    @with_device_message
    def save_config(self, *args):  # pylint: disable=unused-argument
        '''
        Save configuration
        '''
        command_line = helper.build_input_packet('sC')
        # self.communicator.write(command_line)
        # result = self.get_input_result('sC', timeout=2)
        result = yield self._message_center.build(command=command_line, timeout=2)

        data = result['data']
        error = result['error']
        if data:
            yield {
                'packetType': 'success',
                'data': error
            }

        yield {
            'packetType': 'success',
            'data': error
        }

    @with_device_message
    def reset_params(self, params, *args):  # pylint: disable=unused-argument
        '''
        Reset params to default
        '''
        command_line = helper.build_input_packet('rD')
        result = yield self._message_center.build(command=command_line, timeout=2)

        error = result['error']
        data = result['data']
        if error:
            yield {
                'packetType': 'error',
                'data': {
                    'error': error
                }
            }

        yield {
            'packetType': 'success',
            'data': data
        }

    def upgrade_framework(self, params, *args):  # pylint: disable=unused-argument
        '''
        Upgrade framework
        '''
        file = ''
        if isinstance(params, str):
            file = params

        if isinstance(params, dict):
            file = params['file']

        # start a thread to do upgrade
        if not self.is_upgrading:
            self.is_upgrading = True
            self._message_center.pause()

            if self._logger is not None:
                self._logger.stop_user_log()

            self.thread_do_upgrade_framework(file)
            print("Upgrade beidou firmware started at:[{0}].".format(
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        return {
            'packetType': 'success'
        }
