import os
import struct
import time
import json
import datetime
import threading
import math
import struct
from ...framework.utils import (helper, resource)
from ...framework.context import APP_CONTEXT
from ..configs.ins401_predefine import (APP_STR, get_ins502_products,
                                        get_ins502_configuratin_file_mapping)
from ..decorator import with_device_message
from ..parsers.ins401_field_parser import encode_value
from ...framework.utils.print import (
    print_yellow, print_green, print_blue, print_red)
from ..ins401.ethernet_provider_base import Provider_base

GNZDA_DATA_LEN = 39


class Provider(Provider_base):
    '''
    INS502 Ethernet 100base-t1 provider
    '''

    def __init__(self, communicator, *args):
        super(Provider, self).__init__(communicator)
        self.type = 'INS502'
        self.prepare_folders()
        self.rtcm_rover2_logf = None

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

        all_products = get_ins502_products()
        config_file_mapping = get_ins502_configuratin_file_mapping()

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

    def load_properties(self):
        # Load config from user working path
        local_config_file_path = os.path.join(os.getcwd(), 'ins502.json')
        if os.path.isfile(local_config_file_path):
            with open(local_config_file_path) as json_data:
                self.properties = json.load(json_data)
                return

        # Load the openimu.json based on its app
        product_name = self.device_info['name']
        app_name = 'RTK_INS'  # self.app_info['app_name']
        app_file_path = os.path.join(self.setting_folder_path, product_name,
                                     app_name, 'ins502.json')

        with open(app_file_path) as json_data:
            self.properties = json.load(json_data)

        if not self.is_app_matched:
            print_yellow(
                'Failed to extract app version information from unit.'
            )

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
                file_name = self.data_folder + '/' + 'ins502_log_' + dir_time
                os.mkdir(file_name)
                self.rtk_log_file_name = file_name

                self.ins401_log_file_path = file_name + '/' + 'user_' + file_time + '.bin'
                self.user_logf = open(self.ins401_log_file_path, "wb")
                self.rtcm_logf = open(
                    file_name + '/' + 'rtcm_base_' + file_time + '.bin', "wb")
                self.rtcm_rover_logf = open(
                    file_name + '/' + 'rtcm_rover_' + file_time + '.bin', "wb")
                self.rtcm_rover2_logf = open(
                    file_name + '/' + 'rtcm_rover2_' + file_time + '.bin', "wb")
            if set_user_para and not self.is_upgrading:
                result = self.set_params(
                    self.properties["initial"]["userParameters"])
                ##print('set user para {0}'.format(result))
                if result['packetType'] == 'success':
                    self.save_config()

                # check saved result
                self.check_predefined_result()

            self.set_unit_sn_message()

            if set_mount_angle:
                self.set_mount_angle()
                self.prepare_lib_folder()

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

    def on_receive_output_packet(self, packet_type, data, *args, **kwargs):
        '''
        Listener for getting output packet
        '''
        if packet_type == b'\x06\x0a':
            if self.rtcm_rover_logf:
                self.rtcm_rover_logf.write(bytes(data))
        elif packet_type == b'\x0c\x0a':
            if self.rtcm_rover2_logf:
                self.rtcm_rover2_logf.write(bytes(data))
        else:
            raw_data = kwargs.get('raw')
            if self.user_logf and raw_data:
                self.user_logf.write(bytes(raw_data))

                if self.mountangle:
                    payload_len = struct.unpack('<I', bytes(raw_data[4:8]))[0]
                    self.save_mountangle_file(
                        packet_type, payload_len, raw_data[8:8+payload_len])

                if packet_type == b'\x07\n':
                    if self.cli_options and self.cli_options.set_mount_angle and self.mountangle_thread is None:
                        content = raw_data[8:]
                        big_mountangle_rvb = []
                        for i in range(3):
                            big_mountangle_rvb.append(struct.unpack(
                                '<d', bytes(content[7 + 8 * i:15 + 8 * i]))[0])

                        for i in range(3):
                            self.big_mountangle_rvb[i] = big_mountangle_rvb[i] * \
                                57.29577951308232
                        if self.mountangle:
                            self.mountangle.mountangle_logger.debug("[mountangle] big_mountangle_rvb: {0}, {1}, {2}".format(
                                self.big_mountangle_rvb[0], self.big_mountangle_rvb[1], self.big_mountangle_rvb[2]))
                        self.start_mountangle_parse()

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
        self.sdk_2_upgrade_flag = False
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

                if param == 'sdk_2':
                    self.sdk_2_upgrade_flag = True

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
            self.sdk_2_upgrade_flag = True
            self.imu_upgrade_flag = False
            self.imu_boot_upgrade_flag = False

        # start a thread to do upgrade
        if not self.is_upgrading:
            self.is_upgrading = True
            self._message_center.pause()
            self.loop_upgrade_flag = True

            if self._logger is not None:
                self._logger.stop_user_log()

            self.thread_do_upgrade_framework(file)
            print("Upgrade INS502 firmware started at:[{0}].".format(
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        return {'packetType': 'success'}

    def configure_algorithm(self, params, *args):
        file = ''
        if isinstance(params[1], str):
            file = params[1]

        can_download, content = self.download_firmware(file)
        if not can_download:
            print_red('Cannot find configuration file')
            return False

        content_size = len(content)
        block_size = 1024
        block_number = math.ceil(content_size/block_size)
        step_result = False
        # send prepare command
        step_result = self.configure_do_send_prepare(
            content_size, block_number)
        if not step_result:
            print_red('Failed to prepare configration')
            return False

        # send packet command
        step_result = self.configure_do_send_packet(content, block_size)
        if not step_result:
            print_red('Failed to send configuration packet')
            return False

        print('Configure succeed, restarting...')
        # do reset
        step_result = self.configure_do_reset()
        if not step_result:
            print_red('Restart failed')
            return False

        print_green('Restart succeed')
        return True

    def configure_do_send_prepare(self, content_size, block_number):
        content_size_bytes = struct.pack('<H', content_size)
        message_bytes = bytes([0x0a, block_number]) + content_size_bytes
        result = self.send_configure_command(message_bytes)

        if result['packetType'] == 'error':
            return False

        if result['data'][0] != 0x0a:
            return False

        return True

    def configure_do_send_packet(self, content, block_size):
        index = 1
        start = 0
        while start < len(content):
            actual_size = min(block_size, len(content)-start)
            message_bytes = bytes([0x0b, index]) + \
                content[start:start+actual_size]
            result = self.send_configure_command(message_bytes)
            if result['packetType'] == 'error':
                return False

            if result['data'][0] != 0x0b:
                return False

            if result['data'][1] != index:
                return False

            index += 1
            start += actual_size

        return True

    def configure_do_reset(self):
        # reset device
        self.send_system_reset_command()
        # ping device
        return self.ping_device(timeout=15)

    def ping_device(self, timeout):
        start_time = datetime.datetime.now()
        while True:
            if (datetime.datetime.now() - start_time).total_seconds() > timeout:
                return False

            result = self.send_ping_command()
            if result['packetType'] == 'success':
                return True

            time.sleep(1)

    @with_device_message
    def send_configure_command(self, message_bytes):
        command_config = b'\xa4\x0a'

        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            command_config, list(message_bytes)
        )

        result = yield self._message_center.build(command=command_line.actual_command)

        error = result['error']
        data = result['data']
        response_code = -1

        if error:
            yield {'packetType': 'error', 'data': data}

        try:
            if data[0] == 0x0a:
                response_code = struct.unpack('<H', data[1:3])[0]
            if data[0] == 0x0b:
                response_code = struct.unpack('<H', data[2:4])[0]
        except:
            yield {'packetType': 'error', 'data': response_code}

        if response_code > 0:
            yield {'packetType': 'error', 'data': response_code}

        yield {'packetType': 'success', 'data': data}

    @with_device_message
    def send_ping_command(self):
        command_ping = b'\x01\xcc'

        command_line = helper.build_ethernet_packet(
            self.communicator.get_dst_mac(),
            self.communicator.get_src_mac(),
            command_ping
        )
        # self.communicator.write(command.actual_command)
        result = yield self._message_center.build(command=command_line.actual_command)

        error = result['error']
        data = result['data']

        if error:
            yield {'packetType': 'error', 'data': data}

        yield {'packetType': 'success', 'data': data}
