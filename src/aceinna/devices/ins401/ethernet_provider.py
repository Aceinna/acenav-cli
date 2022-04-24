import os
import struct
import time
import json
import datetime
import threading
import math
import re
import struct
from ..widgets import (NTRIPClient, EthernetDataLogger,
                       EthernetDebugDataLogger, EthernetRTCMDataLogger)
from ...framework.utils import (helper, resource)
from ...framework.context import APP_CONTEXT
from ...framework.utils.firmware_parser import parser as firmware_content_parser
from ..base.provider_base import OpenDeviceBase
from ..configs.ins401_predefine import (APP_STR, get_ins401_products,
                                         get_configuratin_file_mapping)
from ..decorator import with_device_message
from ...models import InternalCombineAppParseRule
from ..parsers.ins401_field_parser import encode_value
from ...framework.utils.print import (print_yellow, print_green, print_blue)
from ..ins401.mountangle.mountangle import MountAngle
from ..upgrade_workers import (
    EthernetSDK9100UpgradeWorker,
    FirmwareUpgradeWorker,
    JumpBootloaderWorker,
    JumpApplicationWorker,
    UPGRADE_EVENT,
    UPGRADE_GROUP
)

GNZDA_DATA_LEN = 39

class Provider(OpenDeviceBase):
    '''
    INS401 Ethernet 100base-t1 provider
    '''

    def __init__(self, communicator, *args):
        super(Provider, self).__init__(communicator)
        self.type = 'INS401'
        self.server_update_rate = 100
        self.sky_data = []
        self.pS_data = []
        self.app_config_folder = ''
        self.device_info = None
        self.app_info = None
        self.compile_info = None
        self.parameters = None
        self.setting_folder_path = None
        self.data_folder = None
        self.debug_serial_port = None
        self.rtcm_serial_port = None
        self.user_logf = None
        self.debug_logf = None
        self.rtcm_logf = None
        self.debug_c_f = None
        self.enable_data_log = False
        self.is_app_matched = False
        self.ntrip_client_enable = False
        self.nmea_buffer = []
        self.nmea_sync = 0
        self.prepare_folders()
        self.ntrip_client = None
        self.connected = True
        self.rtk_log_file_name = ''
        self.rtcm_rover_logf = None
        self.big_mountangle_rvb = [0, 0, 0]
        self.ins_save_logf = None
        self.ins401_log_file_path = None
        self.mountangle_thread = None
        self.mountangle= None
        self.f_process = None
        self.rtk_upgrade_flag = False
        self.ins_upgrade_flag = False
        self.sdk_upgrade_flag = False
        self.imu_upgrade_flag = False
        self.imu_boot_upgrade_flag = False
        self.unit_sn = None
        self.bootloader_version = None
        self.rtk_crc = []
        self.ins_crc = []
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
        self.setting_folder_path = os.path.join(executor_path,
                                                setting_folder_name)

        all_products = get_ins401_products()
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
                        os.path.join(product, app_name,
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

        self._device_info_string = '# Connected {0} with ethernet #\n\rDevice: {1} \n\rFirmware: {2}'\
            .format('INS401', device_info, app_info)

        return self._device_info_string

    def bind_compile_info(self, compile_info):
        compile_info_str = str(compile_info, encoding='utf-8')
        compile_info_str = compile_info_str.replace('\x0b','\\')
        self._build_compile_info(compile_info_str)
        return (compile_info_str)
    def _build_compile_info(self, text):
        '''
        Build compile info
        '''
        split_text = text.split(',')
        self.compile_info = {
            'ins_lib':{
                'version': split_text[0],
                'time': split_text[1],
                'author': split_text[2],
                'commit':split_text[3]
            },
            'ins_app':{
                'version': split_text[4],
                'time': split_text[5],
                'author': split_text[6],
                'commit':split_text[7]
            },
            'rtk_lib':{
                'version': split_text[8],
                'time': split_text[9],
                'author': split_text[10],
                'commit':split_text[11]
            },
            'rtk_app':{
                'version': split_text[12],
                'time': split_text[13],
                'author': split_text[14],
                'commit':split_text[15]
            }
        }        
        print(self.compile_info)
    def _build_device_info(self, text):
        '''
        Build device info
        '''
        if text.__contains__('SN:'):
            split_text = text.split(' ')
            sn_split_text = text.split('SN:')
            self.unit_sn = sn_split_text[1]

            self.device_info = {
                'name': split_text[0],
                'pn': split_text[2],
                'sn': sn_split_text[1]
            }
        else:
            split_text = text.split(' ')
            self.unit_sn = split_text[2]

            self.device_info = {
                'name': split_text[0],
                'pn': split_text[1],
                'sn': split_text[2],
                'hardware':split_text[4]
            }

    def _build_app_info(self, text):
        '''
        Build app info
        '''
        if text.__contains__('SN:'):
            self.app_info = {
                'version': 'bootloader'
            }
            
            return

        app_version = text
        
        split_text = app_version.split(' ')
        app_name = next((item for item in APP_STR if item in split_text), None)

        if not app_name:
            app_name = 'RTK_INS'
            self.is_app_matched = False
        else:
            self.is_app_matched = True

        self.app_info = {
            'app_name': app_name,
            'firmware':  split_text[2],
            'bootloader': split_text[4],
        }

    def load_properties(self):
        # Load config from user working path
        local_config_file_path = os.path.join(os.getcwd(), 'ins401.json')
        if os.path.isfile(local_config_file_path):
            with open(local_config_file_path) as json_data:
                self.properties = json.load(json_data)
                return

        # Load the openimu.json based on its app
        product_name = self.device_info['name']
        app_name = 'RTK_INS'  # self.app_info['app_name']
        app_file_path = os.path.join(self.setting_folder_path, product_name,
                                     app_name, 'ins401.json')

        with open(app_file_path) as json_data:
            self.properties = json.load(json_data)

        if not self.is_app_matched:
            print_yellow(
                'Failed to extract app version information from unit.'
            )

    def ntrip_client_thread(self): 
        self.ntrip_client = NTRIPClient(self.properties)
        self.ntrip_client.on('parsed', self.handle_rtcm_data_parsed)
        if self.device_info.__contains__('sn') and self.device_info.__contains__('pn'):
            self.ntrip_client.set_connect_headers({
                'Ntrip-Sn': self.device_info['sn'],
                'Ntrip-Pn': self.device_info['pn']
            })
        self.ntrip_client.run()

    def handle_rtcm_data_parsed(self, data):
        # print('rtcm',data)

        if not self.is_upgrading and not self.with_upgrade_error:
            if self.rtcm_logf is not None and data is not None:
                self.rtcm_logf.write(bytes(data))
                self.rtcm_logf.flush()

            if self.communicator.can_write():
                command = helper.build_ethernet_packet(
                    self.communicator.get_dst_mac(),
                    self.communicator.get_src_mac(), b'\x02\x0b', data)

                self.communicator.write(command.actual_command)

    def after_setup(self):
        set_user_para = self.cli_options and self.cli_options.set_user_para
        self.ntrip_client_enable = self.cli_options and self.cli_options.ntrip_client
        # with_raw_log = self.cli_options and self.cli_options.with_raw_log
        set_mount_angle = self.cli_options and self.cli_options.set_mount_angle

        try:
            if self.data_folder:
                dir_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                file_time = time.strftime("%Y_%m_%d_%H_%M_%S",
                                          time.localtime())
                file_name = self.data_folder + '/' + 'ins401_log_' + dir_time
                os.mkdir(file_name)
                self.rtk_log_file_name = file_name

                self.ins401_log_file_path = file_name + '/' + 'user_' + file_time + '.bin'
                self.user_logf = open(self.ins401_log_file_path, "wb")
                self.rtcm_logf = open(
                    file_name + '/' + 'rtcm_base_' + file_time + '.bin', "wb")
                self.rtcm_rover_logf = open(
                    file_name + '/' + 'rtcm_rover_' + file_time + '.bin', "wb")
                self.ins_save_logf = open(
                    file_name + '/' + 'ins_save_' + file_time + '.bin', "wb")
            if set_user_para:
                result = self.set_params(
                    self.properties["initial"]["userParameters"])
                ##print('set user para {0}'.format(result))
                if result['packetType'] == 'success':
                    self.save_config()

                # check saved result
                self.check_predefined_result()


            if set_mount_angle:
                self.set_mount_angle()
                self.prepare_lib_folder()

            if not self.is_in_bootloader:
                result = self.get_ins_message()
                if result['packetType'] == 'success':
                    #print('data = ',bytes(result['data']))
                    self.ins_save_logf.write(bytes(result['raw_data']))
                    self.ins_save_logf.flush() 
                else:
                    print('can\'t get ins save message')
            if self.cli_options.debug == 'true':
                result = self.get_compile_message()
                if result['packetType'] == 'success':
                    format_compile_info = self.bind_compile_info(
                        result['data'])
                    print_blue(format_compile_info)
                else:
                    print('can\'t get get_compile_message')
            self.save_device_info()

            # start ntrip client
            if not self.is_upgrading and not self.with_upgrade_error:
                # start ntrip client
                if self.properties["initial"].__contains__("ntrip") \
                    and not self.ntrip_client \
                    and not self.is_in_bootloader \
                    and not self.cli_options.use_cli:

                    threading.Thread(target=self.ntrip_client_thread).start()

        except Exception as e:
            print('Exception in after setup', e)
            return False


    def nmea_checksum(self, data):
        nmea_str = data[1:len(data) - 2]
        nmeadata = nmea_str[0:len(nmea_str)-3]
        cksum = nmea_str[len(nmea_str)-2:len(nmea_str)]

        calc_cksum = 0
        for s in nmeadata:
            calc_cksum ^= ord(s)
        return int(cksum, 16), calc_cksum

    def on_read_raw(self, data):
        if data[0] != 0x24 or data[1] != 0x47:
            return
        
        temp_str_nmea = data.decode('utf-8')
        if (temp_str_nmea.find("\r\n", len(temp_str_nmea)-2, len(temp_str_nmea)) != -1):
            str_nmea = temp_str_nmea 
        else:
            result = temp_str_nmea.find("\r\n", GNZDA_DATA_LEN-10, GNZDA_DATA_LEN)
            if result != -1:
                str_nmea = temp_str_nmea[0:result + 2]
            else:
                return

        try:
            cksum, calc_cksum = self.nmea_checksum(str_nmea)
            if cksum == calc_cksum:
                if str_nmea.find("$GPGGA", 0, 6) != -1 or str_nmea.find("$GNGGA", 0, 6) != -1:
                    if self.ntrip_client:
                        self.ntrip_client.send(str_nmea)
                if self.user_logf:
                    self.user_logf.write(data)
            
            APP_CONTEXT.get_print_logger().info(str_nmea[0:len(str_nmea) - 2])
        except Exception as e:
            print('NMEA fault:{0}'.format(e))


    def thread_data_log(self, *args, **kwargs):
        self.ethernet_data_logger = EthernetDataLogger(self.properties,
                                                       self.communicator,
                                                       self.user_logf)
        self.ethernet_data_logger.run()

    def thread_debug_data_log(self, *args, **kwargs):
        self.ethernet_debug_data_logger = EthernetDebugDataLogger(
            self.properties, self.communicator, self.debug_logf)
        self.ethernet_debug_data_logger.run()

    def thread_rtcm_data_log(self, *args, **kwargs):
        self.ethernet_rtcm_data_logger = EthernetRTCMDataLogger(
            self.properties, self.communicator, self.rtcm_logf)
        self.ethernet_rtcm_data_logger.run()
        
    def set_mountangle_config(self, result = []):
        # copy contents of app_config under executor path
        setting_folder_path = os.path.join(resource.get_executor_path(),
                                                'setting')
        # Load the openimu.json based on its app
        product_name = 'INS401'
        app_name = 'RTK_INS'  # self.app_info['app_name']
        app_file_path = os.path.join(setting_folder_path, product_name,
                                        app_name, 'ins401.json')

        with open(app_file_path, 'r') as json_data:
            self.properties = json.load(json_data)
        
        # update mountangle config file
        with open(app_file_path, 'w') as json_data: 
            userParameters = self.properties["initial"]["userParameters"]   
            for i in range(3):
                userParameters[9 + i]['value'] = result[i]
            
            json.dump(self.properties, 
                    json_data,
                    indent=4,
                    ensure_ascii=False)

        # setting params
        with open(app_file_path, 'r') as json_data:
            self.properties = json.load(json_data)

        result = self.set_params(self.properties["initial"]["userParameters"])
        if result['packetType'] == 'success':
            self.save_config()

        # check saved result
        self.check_predefined_result()


    def save_mountangle_file(self, type, length, content):
        ''' Parse final packet
        '''
        if type == b'\x01\n': # imu
            b = struct.pack('{0}B'.format(length), *content)
            data = struct.unpack('<HIffffff', b)

            buffer = format(data[0], '') + ","\
                + format(data[1]/1000, '11.4f') + "," + "    ,"\
                + format(data[2], '14.10f') + ","\
                + format(data[3], '14.10f') + ","\
                + format(data[4], '14.10f') + ","\
                + format(data[5], '14.10f') + ","\
                + format(data[6], '14.10f') + ","\
                + format(data[7], '14.10f') + "\n"
            self.f_process.write('$GPIMU,' + buffer)

        elif type == b'\x02\n':
            b = struct.pack('{0}B'.format(length), *content)
            data = struct.unpack('<HIBdddfffBBffffffff', b)

            buffer = '$GPGNSS,' + format(data[0], '') + ","\
                + format(data[1]/1000, '11.4f') + ","\
                + format(data[3], '14.9f') + ","\
                + format(data[4], '14.9f') + ","\
                + format(data[5], '10.4f') + ","\
                + format(data[6], '10.4f') + ","\
                + format(data[7], '10.4f') + ","\
                + format(data[8], '10.4f') + ","\
                + format(data[2], '3') + "\n"
            self.f_process.write(buffer)

            horizontal_speed = math.sqrt(data[13] * data[13] + data[14] * data[14])
            track_over_ground = math.atan2(data[14], data[13]) * (57.295779513082320)
            buffer = '$GPVEL,' + format(data[0], '') + ","\
                + format(data[1]/1000, '11.4f') + ","\
                + format(horizontal_speed, '10.4f') + ","\
                + format(track_over_ground, '10.4f') + ","\
                + format(data[15], '10.4f') + "\n"
            self.f_process.write(buffer)

        elif type == b'\x03\n':
            b = struct.pack('{0}B'.format(length), *content)
            data = struct.unpack('<HIBBdddfffffffffffffffffff', b)

            if (data[1]%100) < 10:
                buffer = format(data[0], '') + ","\
                    + format(data[1]/1000, '11.4f') + ","\
                    + format(data[4], '14.9f') + ","\
                    + format(data[5], '14.9f') + ","\
                    + format(data[6], '10.4f') + ","\
                    + format(data[7], '10.4f') + ","\
                    + format(data[8], '10.4f') + ","\
                    + format(data[9], '10.4f') + ","\
                    + format(data[12], '10.4f') + ","\
                    + format(data[13], '10.4f') + ","\
                    + format(data[14], '10.4f') + ","\
                    + format(data[3], '3')
                self.f_process.write('$GPINS,' + buffer + "\n")

                self.mountangle.process_live_data(data, 1)

        elif type == b'\x04\n':
            b = struct.pack('{0}B'.format(length), *content)
            data = struct.unpack('<HIBdBQ', b)

            buffer = format(data[0], '') + ","\
                + format(data[1]/1000, '11.4f') + ","\
                + format(data[2], '3') + ","\
                + format(data[3], '10.4f') + ","\
                + format(data[4], '3') + ","\
                + format(data[5], '16') + "\n"

            self.f_process.write('$GPODO,' + buffer)
        
        elif type == b'\x05\n':
            pass

        elif type == b'\x06\n': # rover rtcm
            pass

        elif type == b'\x07\n': # corr imu
            pass

    def mountangle_parse_thread(self):       
        print('processing {0}\n'.format(self.ins401_log_file_path))
        
        path = mkdir(self.ins401_log_file_path)

        temp_file_path, temp_fname = os.path.split(self.ins401_log_file_path)
        fname, ext = os.path.splitext(temp_fname)
        self.f_process = open(path + '/' + fname + '-process', 'w+')

        self.mountangle = MountAngle(os.getcwd(), path,  path + '/' + fname + '-process')
        self.mountangle.mountangle_set_parameters(self.big_mountangle_rvb)
        self.mountangle.mountangle_run()

        while True:
            if self._message_center._is_stop:
                time.sleep(1)
                continue 

            if self.mountangle.out_result_flag:
                rvb = []
                for i in range(3):
                    f = self.big_mountangle_rvb[i] -self.mountangle.mountangle_estimate_result[i]
                    rvb.append(float('%.4f'% f))
                
                self.set_mountangle_config(rvb)
                time.sleep(2)
                self.save_device_info()
                time.sleep(2)
                print('mountangle_result:', rvb)
                os._exit(1)

            time.sleep(5)
  
    def start_mountangle_parse(self):
        if self.ins401_log_file_path and self.mountangle_thread is None:
            self.mountangle_thread = threading.Thread(target=self.mountangle_parse_thread)
            self.mountangle_thread.start()

    def on_receive_output_packet(self, packet_type, data, *args, **kwargs):
        '''
        Listener for getting output packet
        '''
        if packet_type == b'\x06\n':
            if self.rtcm_rover_logf:
                self.rtcm_rover_logf.write(bytes(data))
        else:
            raw_data = kwargs.get('raw')
            if self.user_logf and raw_data:
                self.user_logf.write(bytes(raw_data))

                if self.mountangle:
                    payload_len = struct.unpack('<I', bytes(raw_data[4:8]))[0]
                    self.save_mountangle_file(packet_type, payload_len, raw_data[8:8+payload_len])
              
                if packet_type == b'\x07\n':
                    if self.cli_options and self.cli_options.set_mount_angle and self.mountangle_thread is None:
                        content = raw_data[8:]
                        big_mountangle_rvb = []            
                        for i in range(3):
                            big_mountangle_rvb.append(struct.unpack('<d', bytes(content[7 + 8 * i:15 + 8 * i]))[0])

                        for i in range(3):
                            self.big_mountangle_rvb[i] = big_mountangle_rvb[i] * 57.29577951308232
                        if self.mountangle:
                            self.mountangle.mountangle_logger.debug("[mountangle] big_mountangle_rvb: {0}, {1}, {2}".format(self.big_mountangle_rvb[0], self.big_mountangle_rvb[1], self.big_mountangle_rvb[2]))
                        self.start_mountangle_parse()


    def after_jump_bootloader(self):
        time.sleep(3)
        for i in range(100):
            result = self.communicator.reshake_hand()
            if result:
                break
            else:
                time.sleep(0.5)
        time.sleep(3)
        for i in range(3):
            send_command = helper.build_ethernet_packet(
                            dest=bytes([int(x, 16) for x in 'ff:ff:ff:ff:ff:ff'.split(':')]),
                            src=self.communicator.get_src_mac(),
                            message_type=[0x01, 0xcc],
                            message_bytes=[])

            self.communicator.write(send_command.actual_command)

            time.sleep(0.2)
            response = helper.read_untils_have_data(
                self.communicator, [0x01, 0xcc], 10, 1000)
            if response:           
                break
        if response:
            text = helper.format_string(response)
            if text.__contains__('SN:'):
                    split_text = text.split(' ')
                    self.bootloader_version = split_text[2][1:]
        else:
            os._exit(1)
           

    def do_reshake(self):
        '''
            check if in application mode
        '''
        for i in range(100):
            result = self.communicator.reshake_hand()
            if result:
                break
            else:
                time.sleep(0.5)

    def before_write_content(self, core, content_len, ack_enable):
        command_CS = [0x04, 0xaa]

        message_bytes = [ord('C'), ord(core)]
        message_bytes.extend(struct.pack('>I', content_len))

        if self.bootloader_version >= '01.01':
            if core == '0':
                message_bytes.extend([ord('r'), ord('t'), ord('k')])
            elif core == '1':
                message_bytes.extend([ord('i'), ord('n'), ord('s')])
        
        self.communicator.reset_buffer()
        if ack_enable:
            for i in range(3):
                command = helper.build_ethernet_packet(
                    self.communicator.get_dst_mac(),
                    self.communicator.get_src_mac(),
                    command_CS, message_bytes,
                    use_length_as_protocol=self.communicator.use_length_as_protocol)
                time.sleep(1)
                self.communicator.write(command.actual_command)
                time.sleep(1)
                result = helper.read_untils_have_data(
                    self.communicator, command_CS, 100, 200)

                if result:     
                    break
            if result is None:
                print('send cs command failed, core:{0}'.format(ord(core)))
                os._exit(1)
        else:
            command = helper.build_ethernet_packet(
                self.communicator.get_dst_mac(),
                self.communicator.get_src_mac(),
                command_CS, message_bytes,
                use_length_as_protocol=self.communicator.use_length_as_protocol)
            for i in range(3):
                self.communicator.write(command.actual_command)
            time.sleep(0.5)

    def ins_firmware_write_command_generator(self, data_len, current, data):
        command_WA = [0x03, 0xaa]
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('>I', data_len))
        message_bytes.extend(data)
        return helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            command_WA, message_bytes,
            use_length_as_protocol=self.communicator.use_length_as_protocol)

    def imu_firmware_write_command_generator(self, data_len, current, data):
        command_WA = [0x41, 0x57]
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('B', data_len))
        message_bytes.extend(data)
        command = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            command_WA, message_bytes)
        command.packet_type = [0x57, 0x41]
        return command

    def imu_write_reset_command(self):
        command_SR = [0x06, 0xcc]
        message_bytes = []

        command = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            command_SR, message_bytes)
        command.packet_type = [0xcc, 0x06]
        
        for _ in range(3):
            self.communicator.write(command.actual_command)
            time.sleep(0.2)


    def ins_jump_bootloader_command_generator(self):
        return helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            bytes([0x01, 0xaa]),
            use_length_as_protocol=self.communicator.use_length_as_protocol)

    def ins_jump_application_command_generator(self):
        if self.bootloader_version >= '01.01':
            message = self.rtk_crc + self.ins_crc
        else:
            message = []

        return helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            bytes([0x02, 0xaa]),
            message,
            use_length_as_protocol=self.communicator.use_length_as_protocol)

    def imu_jump_bootloader_command_generator(self):
        return helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            bytes([0x49, 0x4a]))

    def imu_jump_application_command_generator(self):
        return helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            bytes([0x41, 0x4a]))

    def get_unit_ethernet_ack_flag(self):
        result = False
        if int(self.unit_sn, 10) <= 2209000531:
            if self.bootloader_version:
                if self.bootloader_version >= '01.02':
                    result = True
                else:                     
                    result = False
            else:
                result = False
        else:
            result = True
                            
        return result

    def build_worker(self, rule, content):
        ''' Build upgarde worker by rule and content
        '''
        if self.communicator.use_length_as_protocol:
            packet_len = 960
        else:
            packet_len = 192

        ethernet_ack_enable = self.get_unit_ethernet_ack_flag()
        if rule == 'rtk' and self.rtk_upgrade_flag:
            rtk_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
                ethernet_ack_enable,
                lambda: helper.format_firmware_content(content),
                self.ins_firmware_write_command_generator,
                packet_len)
            rtk_upgrade_worker.name = 'MAIN_RTK'
            rtk_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(15))
            rtk_upgrade_worker.on(UPGRADE_EVENT.BEFORE_WRITE,
                                lambda: self.before_write_content('0', len(content), ethernet_ack_enable))
            return rtk_upgrade_worker

        if rule == 'ins' and self.ins_upgrade_flag:
            ins_upgrade_worker = FirmwareUpgradeWorker(
                self.communicator,
                ethernet_ack_enable,
                lambda: helper.format_firmware_content(content),
                self.ins_firmware_write_command_generator,
                packet_len)
            ins_upgrade_worker.name = 'MAIN_RTK'
            ins_upgrade_worker.group = UPGRADE_GROUP.FIRMWARE
            ins_upgrade_worker.on(
                UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(15))
            ins_upgrade_worker.on(UPGRADE_EVENT.BEFORE_WRITE,
                                  lambda: self.before_write_content('1', len(content), ethernet_ack_enable))
            return ins_upgrade_worker

        if rule == 'sdk' and self.sdk_upgrade_flag:
            sdk_upgrade_worker = EthernetSDK9100UpgradeWorker(
                self.communicator,
                lambda: helper.format_firmware_content(content))
            sdk_upgrade_worker.group = UPGRADE_GROUP.FIRMWARE
            return sdk_upgrade_worker

        if self.imu_boot_upgrade_flag:
            if rule == 'imu_boot':
                ethernet_ack_enable = True

                imu_boot_upgrade_worker = FirmwareUpgradeWorker(
                    self.communicator,
                    ethernet_ack_enable,
                    lambda: helper.format_firmware_content(content),
                    self.imu_firmware_write_command_generator,
                    192)
                imu_boot_upgrade_worker.name = 'SUB_IMU_BOOT'
                imu_boot_upgrade_worker.group = UPGRADE_GROUP.FIRMWARE
                imu_boot_upgrade_worker.on(
                    UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(8))
                return imu_boot_upgrade_worker
                
        if self.imu_upgrade_flag:
            if rule == 'imu':
                ethernet_ack_enable = True

                imu_upgrade_worker = FirmwareUpgradeWorker(
                    self.communicator,
                    ethernet_ack_enable,
                    lambda: helper.format_firmware_content(content),
                    self.imu_firmware_write_command_generator,
                    192)
                imu_upgrade_worker.name = 'SUB_IMU'
                imu_upgrade_worker.group = UPGRADE_GROUP.FIRMWARE
                imu_upgrade_worker.on(
                    UPGRADE_EVENT.FIRST_PACKET, lambda: time.sleep(8))
                return imu_upgrade_worker

    def get_upgrade_workers(self, firmware_content):
        workers = []

        rules = [
            InternalCombineAppParseRule('rtk', 'rtk_start:', 4),
            InternalCombineAppParseRule('ins', 'ins_start:', 4),
            InternalCombineAppParseRule('sdk', 'sdk_start:', 4),
            InternalCombineAppParseRule('imu_boot', 'imu_boot_start:', 4),
            InternalCombineAppParseRule('imu', 'imu_start:', 4),
        ]

        if self.communicator:
            self.communicator.reset_buffer()
            self.communicator.upgrade()

        parsed_content = firmware_content_parser(firmware_content, rules)

        self.rtk_crc = []
        self.ins_crc = []

        # foreach parsed content, if empty, skip register into upgrade center
        for _, rule in enumerate(parsed_content):
            content = parsed_content[rule]
            if len(content) == 0:
                continue

            if rule == 'rtk':
                rtk_len = len(content) & 0xFFFF
                self.rtk_crc = helper.calc_crc(content[0:rtk_len])
            
            if rule == 'ins':
                ins_len = len(content) & 0xFFFF
                self.ins_crc = helper.calc_crc(content[0:ins_len])

            worker = self.build_worker(rule, content)
            if not worker:
                continue

            workers.append(worker)

        # wrap rtk and ins
        start_index = -1
        end_index = -1
        for i, worker in enumerate(workers):
            if isinstance(worker, FirmwareUpgradeWorker) and worker.name == 'MAIN_RTK':
                start_index = i if start_index == -1 else start_index
                end_index = i
        if self.is_in_bootloader:
            ins_wait_timeout = 1
        else:
            ins_wait_timeout = 3

        ethernet_ack_enable = self.get_unit_ethernet_ack_flag()

        ins_jump_bootloader_worker = JumpBootloaderWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.ins_jump_bootloader_command_generator,
            listen_packet=[0x01, 0xaa],
            wait_timeout_after_command=ins_wait_timeout)
        ins_jump_bootloader_worker.group = UPGRADE_GROUP.FIRMWARE
        ins_jump_bootloader_worker.on(
            UPGRADE_EVENT.BEFORE_COMMAND, self.do_reshake)
        ins_jump_bootloader_worker.on(
            UPGRADE_EVENT.AFTER_COMMAND, self.after_jump_bootloader)

        ins_jump_application_worker = JumpApplicationWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.ins_jump_application_command_generator,
            listen_packet=[0x02, 0xaa],
            wait_timeout_after_command=4)
        ins_jump_application_worker.group = UPGRADE_GROUP.FIRMWARE
        ins_jump_application_worker.on(
            UPGRADE_EVENT.AFTER_COMMAND, self.do_reshake)

        if start_index > -1 and end_index > -1:
            workers.insert(
                start_index, ins_jump_bootloader_worker)
            workers.insert(
                end_index+2, ins_jump_application_worker)

        # wrap imu booloader
        start_index = -1
        end_index = -1
        for i, worker in enumerate(workers):
            if isinstance(worker, FirmwareUpgradeWorker) and worker.name == 'SUB_IMU_BOOT':
                start_index = i if start_index == -1 else start_index
                end_index = i

        ethernet_ack_enable = True

        imu_boot_jump_bootloader_worker = JumpBootloaderWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.imu_jump_bootloader_command_generator,
            listen_packet=[0x4a, 0x49],
            wait_timeout_after_command=30)
        imu_boot_jump_bootloader_worker.on(
            UPGRADE_EVENT.BEFORE_COMMAND, lambda: time.sleep(1))
        imu_boot_jump_bootloader_worker.group = UPGRADE_GROUP.FIRMWARE

        imu_boot_jump_application_worker = JumpApplicationWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.imu_jump_application_command_generator,
            listen_packet=[0x4a, 0x41])
        imu_boot_jump_application_worker.group = UPGRADE_GROUP.FIRMWARE

        if start_index > -1 and end_index > -1:
            workers.insert(
                start_index, imu_boot_jump_bootloader_worker)
            workers.insert(
                end_index+2, imu_boot_jump_application_worker)

        # wrap imu app
        start_index = -1
        end_index = -1
        for i, worker in enumerate(workers):
            if isinstance(worker, FirmwareUpgradeWorker) and worker.name == 'SUB_IMU':
                start_index = i if start_index == -1 else start_index
                end_index = i

        imu_jump_bootloader_worker = JumpBootloaderWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.imu_jump_bootloader_command_generator,
            listen_packet=[0x4a, 0x49],
            wait_timeout_after_command=30)
        imu_jump_bootloader_worker.on(
            UPGRADE_EVENT.BEFORE_COMMAND, lambda: time.sleep(1))
        imu_jump_bootloader_worker.group = UPGRADE_GROUP.FIRMWARE

        imu_jump_application_worker = JumpApplicationWorker(
            self.communicator,
            ethernet_ack_enable,
            command=self.imu_jump_application_command_generator,
            listen_packet=[0x4a, 0x41])
        imu_jump_application_worker.on(
            UPGRADE_EVENT.AFTER_COMMAND, self.imu_write_reset_command)
        imu_jump_application_worker.group = UPGRADE_GROUP.FIRMWARE

        if start_index > -1 and end_index > -1:
            workers.insert(
                start_index, imu_jump_bootloader_worker)
            workers.insert(
                end_index+2, imu_jump_application_worker)

        return workers

    def get_device_connection_info(self):
        return {
            'modelName': self.device_info['name'],
            'deviceType': self.type,
            'serialNumber': self.device_info['sn'],
            'partNumber': self.device_info['pn'],
            'firmware': self.device_info['firmware_version']
        }

    def get_operation_status(self):
        if self.is_logging:
            return 'LOGGING'

        return 'IDLE'

    def check_predefined_result(self):
        local_time = time.localtime()
        formatted_file_time = time.strftime("%Y_%m_%d_%H_%M_%S", local_time)
        file_path = os.path.join(
            self.rtk_log_file_name,
            'parameters_predefined_{0}.json'.format(formatted_file_time))
        # save parameters to data log folder after predefined parameters setup
        result = self.get_params()
        if result['packetType'] == 'inputParams':
            with open(file_path, 'w') as outfile:
                json.dump(result['data'], outfile, indent=4, ensure_ascii=False)

        # compare saved parameters with predefined parameters
        hashed_predefined_parameters = helper.collection_to_dict(
            self.properties["initial"]["userParameters"], key='paramId')
        hashed_current_parameters = helper.collection_to_dict(result['data'],
                                                              key='paramId')
        success_count = 0
        fail_count = 0
        fail_parameters = []
        for key in hashed_predefined_parameters:
            #print(hashed_current_parameters[key]['name'], 'current:',hashed_current_parameters[key]['value'],'predefined:',hashed_predefined_parameters[key]['value'])
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

    def save_device_info(self):
        ''' Save device configuration
            File name: configuration.json
        '''
        if not self.rtk_log_file_name or not self._device_info_string:
            return

        if self.is_in_bootloader:
            return
        
        result = self.get_params()

        device_configuration = None
        file_path = os.path.join(self.rtk_log_file_name, 'configuration.json')

        if not os.path.exists(file_path):
            device_configuration = []
        else:
            with open(file_path) as json_data:
                device_configuration = (list)(json.load(json_data))

        if result['packetType'] == 'inputParams':
            session_info = dict()
            session_info['time'] = time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime())
            session_info['device'] = self.device_info
            session_info['app'] = self.app_info
            if self.cli_options.debug == 'true':
                session_info['compile'] = self.compile_info
            session_info['interface'] = self.cli_options.interface
            parameters_configuration = dict()
            for item in result['data']:
                param_name = item['name']
                param_value = item['value']
                parameters_configuration[param_name] = param_value

            session_info['parameters'] = parameters_configuration
            device_configuration.append(session_info)

            with open(file_path, 'w') as outfile:
                json.dump(device_configuration,
                          outfile,
                          indent=4,
                          ensure_ascii=False)

    def after_upgrade_completed(self):
        self.do_reshake()
        self.after_setup()

        # start ntrip client
        if self.properties["initial"].__contains__("ntrip") \
            and not self.ntrip_client \
            and not self.is_in_bootloader:
            threading.Thread(target=self.ntrip_client_thread).start()
        
        pass

    # command list
    def server_status(self, *args):  # pylint: disable=invalid-name
        '''
        Get server connection status
        '''
        return {'packetType': 'ping', 'data': {'status': '1'}}

    def get_device_info(self, *args):  # pylint: disable=invalid-name
        '''
        Get device information
        '''
        return {
            'packetType':
            'deviceInfo',
            'data': [{
                'name': 'Product Name',
                'value': self.device_info['name']
            }, {
                'name': 'IMU',
                'value': self.device_info['imu']
            }, {
                'name': 'PN',
                'value': self.device_info['pn']
            }, {
                'name': 'Firmware Version',
                'value': self.device_info['firmware_version']
            }, {
                'name': 'SN',
                'value': self.device_info['sn']
            }, {
                'name': 'App Version',
                'value': self.app_info['version']
            }]
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

        for parameter in self.properties['userConfiguration']:
            if parameter['paramId'] == 0:
                continue
            result = self.get_param(parameter)
            if result['packetType'] == 'error':
                has_error = True
                break

            parameter_values.append(result['data'])
            time.sleep(0.3)

        if not has_error:
            self.parameters = parameter_values
            yield {'packetType': 'inputParams', 'data': parameter_values}

        yield {'packetType': 'error', 'data': 'No Response'}

    @with_device_message
    def get_param(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramter value
        '''
        gP = b'\x02\xcc'
        message_bytes = []
        message_bytes.extend(encode_value('uint32', params['paramId']))
        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            gP, message_bytes)
        result = yield self._message_center.build(command=command_line.actual_command)
        data = result['data']
        error = result['error']

        if error:
            yield {'packetType': 'error', 'data': 'No Response'}

        if data:
            self.parameters = data
            yield {'packetType': 'inputParam', 'data': data}

        yield {'packetType': 'error', 'data': 'No Response'}

    @with_device_message
    def set_params(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramters value
        '''
        input_parameters = self.properties['userConfiguration']

        for parameter in params:
            exist_parameter = next((x for x in input_parameters
                                    if x['paramId'] == parameter['paramId']),
                                   None)

            if exist_parameter:
                parameter['type'] = exist_parameter['type']
                result = self.set_param(parameter)
                # print('result:', result)

                packet_type = result['packetType']
                data = result['data']

                if packet_type == 'error':
                    yield {'packetType': 'error', 'data': {'error': data}}
                    break

                if data['error'] > 0:
                    yield {'packetType': 'error', 'data': {'error': data}}
                    break
            time.sleep(0.1)

        yield {'packetType': 'success', 'data': {'error': 0}}

    @with_device_message
    def set_param(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramter value
        '''
        uP = b'\x03\xcc'
        message_bytes = []
        message_bytes.extend(encode_value('uint32', params['paramId']))
        message_bytes.extend(encode_value(params['type'], params['value']))
        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            uP, message_bytes)
        result = yield self._message_center.build(command=command_line.actual_command)

        error = result['error']
        data = result['data']
        if error:
            yield {'packetType': 'error', 'data': {'error': data}}

        yield {'packetType': 'success', 'data': {'error': data}}

    @with_device_message
    def save_config(self, *args):  # pylint: disable=unused-argument
        '''
        Save configuration
        '''
        sC = b'\x04\xcc'
        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            sC)

        # self.communicator.write(command_line)
        # result = self.get_input_result('sC', timeout=2)
        result = yield self._message_center.build(command=command_line.actual_command,
                                                  timeout=2)

        data = result['data']
        error = result['error']
        if error:
            yield {'packetType': 'error', 'data': data}

        yield {'packetType': 'success', 'data': data}
    @with_device_message
    def set_mount_angle(self, *args):  # pylint: disable=unused-argument
        '''
        Save configuration
        '''
        sC = b'\x05\xcc'
        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            sC)

        result = yield self._message_center.build(command=command_line.actual_command,
                                                  timeout=2)

        data = result['data']
        error = result['error']
        print('set mount angle result:', data)
        if error:
            yield {'packetType': 'error', 'data': data}

        yield {'packetType': 'success', 'data': data}
    @with_device_message
    def get_ins_message(self):
        command_gi = b'\x09\x0a'

        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            command_gi)
        result = yield self._message_center.build(command=command_line.actual_command, timeout=3)
        error = result['error']
        data = result['data']
        raw_data = result['raw']
        if error:
            yield {'packetType': 'error', 'data': {'error': error}, 'raw_data': {'error': error}}

        yield {'packetType': 'success', 'data': data, 'raw_data': raw_data}


    @with_device_message
    def get_compile_message(self):
        command_gc = b'\x09\xaa'

        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(), self.communicator.get_src_mac(),
            command_gc)
        result = yield self._message_center.build(command=command_line.actual_command, timeout=3)
        error = result['error']
        data = result['data']
        raw_data = result['raw']
        if error:
            yield {'packetType': 'error', 'data': {'error': error}, 'raw_data': {'error': error}}

        yield {'packetType': 'success', 'data': data, 'raw_data': raw_data}

    @with_device_message
    def reset_params(self, params, *args):  # pylint: disable=unused-argument
        '''
        Reset params to default
        '''
        raise Exception('Not implemented')

    def upgrade_framework(self, params, *args):  # pylint: disable=unused-argument
        '''
        Upgrade framework
        '''
        file = ''
        if isinstance(params[1], str):
            file = params[1]

        if isinstance(params[1], dict):
            file = params[1]['file']
        
        self.rtk_upgrade_flag = False
        self.ins_upgrade_flag = False
        self.sdk_upgrade_flag = False
        self.imu_upgrade_flag = False
        self.imu_boot_upgrade_flag = False

        if len(params) > 2: 
            # rtk ins sdk imu  each upgrade
            for param in params:   
                if param == 'rtk':
                    self.rtk_upgrade_flag = True

                if param == 'ins':
                    self.ins_upgrade_flag = True

                if param == 'sdk':
                    self.sdk_upgrade_flag = True 

                if param == 'imu_boot':
                    self.imu_boot_upgrade_flag = True 

                if param == 'imu':
                    self.imu_upgrade_flag = True

        elif len(params) == 2:    
            # rtk ins sdk imu upgrade, the imu boot upgrade depends on 
            # whether the imu boot is merged into the firmware
            self.rtk_upgrade_flag = True
            self.ins_upgrade_flag = True
            self.sdk_upgrade_flag = True
            self.imu_upgrade_flag = True
            self.imu_boot_upgrade_flag = True

        # start a thread to do upgrade
        if not self.is_upgrading:
            self.is_upgrading = True
            self._message_center.pause()

            if self._logger is not None:
                self._logger.stop_user_log()

            self.thread_do_upgrade_framework(file)
            print("Upgrade INS401 firmware started at:[{0}].".format(
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        return {'packetType': 'success'}

    @with_device_message
    def send_command(self, command_line):
        # command_line = #build a command
        # helper.build_input_packet('rD')
        result = yield self._message_center.build(command=command_line,
                                                  timeout=5)

        error = result['error']
        data = result['data']
        if error:
            yield {'packetType': 'error', 'data': {'error': error}}

        yield {'packetType': 'success', 'data': data}
    
    def prepare_lib_folder(self):
        executor_path = resource.get_executor_path()
        lib_folder_name = 'libs'

        # copy contents of libs file under executor path
        lib_folder_path = os.path.join(
            executor_path, lib_folder_name)

        if not os.path.isdir(lib_folder_path):
            os.makedirs(lib_folder_path)

        DR_lib_file = "DR_MountAngle"
        INS_lib_file = "INS"
        if os.name == 'nt':  # windows
            DR_lib_file = "DR_MountAngle.dll"
            INS_lib_file = "INS.dll"

        DR_lib_path = os.path.join(lib_folder_path, DR_lib_file)
        if not os.path.isfile(DR_lib_path):
            lib_content = resource.get_content_from_bundle(
                lib_folder_name, DR_lib_file)
            if lib_content is None:
                raise ValueError('Lib file content is empty')

            with open(DR_lib_path, "wb") as code:
                code.write(lib_content)


        INS_lib_path = os.path.join(lib_folder_path, INS_lib_file)
        if not os.path.isfile(INS_lib_path):
            lib_content = resource.get_content_from_bundle(
                lib_folder_name, INS_lib_file)
            if lib_content is None:
                raise ValueError('Lib file content is empty')

            with open(INS_lib_path, "wb") as code:
                code.write(lib_content)
        
        if DR_lib_path and INS_lib_path:
            return True

        return False
