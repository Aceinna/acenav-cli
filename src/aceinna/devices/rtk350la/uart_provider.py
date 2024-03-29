import time
import serial
import struct
from ..decorator import with_device_message
from ..base.rtk_provider_base import RTKProviderBase
from ..upgrade_workers import (
    FirmwareUpgradeWorker,
    SDK9100UpgradeWorker,
    UPGRADE_EVENT,
    UPGRADE_GROUP
)
from ...framework.utils import (
    helper
)
from ...framework.utils.print import print_red
from ..parsers.rtk330l_field_parser import encode_value, get_value_len
from ...framework.context import APP_CONTEXT
from ...framework.utils.print import (print_green, print_yellow, print_red)
import threading
import os
from ..parsers.rtk350l_message_parser import UartMessageParser as Rtk350lUartMessageParser

class Provider(RTKProviderBase):
    '''
    RTK350LA UART provider
    '''

    def __init__(self, communicator, *args):
        super(Provider, self).__init__(communicator)
        self.type = 'RTK350LA'
        self.bootloader_baudrate = 460800
        self.config_file_name = 'RTK350LA.json'
        self.device_category = 'RTK350LA'
        self.port_index_define = {
            'user': 0,
            'rtcm': -2,
            'debug': 1,
        }
        self.user_logf = None
        #self.user2_logf = None
        self.rtcm_rover_logf = None
        self.rtcm_rover2_logf = None


    @with_device_message
    def get_params(self, *args):  # pylint: disable=unused-argument
        '''
        Get all parameters
        '''
        has_error = False
        parameter_values = []

        if self.app_info['app_name'] == 'RTK_INS':
            conf_parameters = self.properties['userConfiguration']
            conf_parameters_len = len(conf_parameters)-1
            step = 10

            for i in range(2, conf_parameters_len, step):
                start_byte = i
                end_byte = i+step-1 if i+step < conf_parameters_len else conf_parameters_len
                time.sleep(0.2)

                para_num = end_byte - start_byte + 1
                message_bytes = []
                message_bytes.append(para_num)
                for i in range(start_byte, end_byte+1):
                    message_bytes.append(i)
                command_line = helper.build_packet(
                    'gB', message_bytes)
                result = yield self._message_center.build(command=command_line, timeout=20)
                if result['error']:
                    has_error = True
                    break

                parameter_values.extend(result['data'])
        else:
            command_line = helper.build_input_packet('gA')
            result = yield self._message_center.build(command=command_line, timeout=5)
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
                    encode_value('uint8', get_value_len(parameter['type']))
                )

                message_bytes.extend(
                    encode_value(parameter['type'], parameter['value'])
                )
                # print('parameter type {0}, value {1}'.format(
                #     parameter['type'], parameter['value']))

            command_line = helper.build_packet(
                'uB', message_bytes)
            # hex_command = [hex(ele) for ele in command_line ]
            # print(hex_command)
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

    def thread_debug_port_receiver(self, formatted_file_time, *args, **kwargs):
        self.rtcm_rover2_logf = open(
                os.path.join(self.rtk_log_file_name, 'rtcm_rover2_{0}.bin'.format(
                    formatted_file_time)), "wb")
        # self.user2_logf = open(
        #         os.path.join(self.rtk_log_file_name, 'user_slave_{0}.bin'.format(
        #             formatted_file_time)), "wb")

        def on_continuous_message_received(packet_type, data, event_time, raw):
            if packet_type == 'rR':
                self.rtcm_rover2_logf.write(bytes(data))
            # else:
            #     if self.user2_logf and raw:
            #         self.user2_logf.write(bytes(raw))


        # build a parser
        parser = Rtk350lUartMessageParser(self.properties)
        parser.on('continuous_message', on_continuous_message_received)

        # log data
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.debug_serial_port.read_all())
                parser.analyse(data)

            except Exception as e:
                print_red('DEBUG PORT Thread error: {0}'.format(e))
                return  # exit thread receiver

            time.sleep(0.001)

    def before_write_content(self, core, content_len):
        self.communicator.serial_port.baudrate = self.bootloader_baudrate
        self.communicator.serial_port.reset_input_buffer()

        message_bytes = [ord('C'), ord(core)]
        message_bytes.extend(struct.pack('>I', content_len))
        command_line = helper.build_packet('CS', message_bytes)
        for i in range(5):
            self.communicator.write(command_line, True)
            time.sleep(1)
            result = helper.read_untils_have_data(
                self.communicator, 'CS', 200, 100)
            if result:
                break

        if not result:
            raise Exception('Cannot run set core command')

    def firmware_write_command_generator(self, data_len, current, data):
        command_WA = 'WA'
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('B', data_len))
        message_bytes.extend(data)
        return helper.build_packet(command_WA, message_bytes)

    # override
    def build_worker(self, rule, content):
        pass

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
            self.rtk_log_file_name = os.path.join(
                self.data_folder, '{0}_log_{1}'.format(self.device_category.lower(), formatted_dir_time))
            os.mkdir(self.rtk_log_file_name)
        except:
            raise Exception(
                'Cannot create log folder, please check if the application has create folder permission')

        # set parameters from predefined parameters
        if set_user_para:
            result = self.set_params(
                self.properties["initial"]["userParameters"])
            if (result['packetType'] == 'success'):
                self.save_config()

            # check saved result
            self.check_predefined_result()

        # start ntrip client
        if self.properties["initial"].__contains__("ntrip") \
            and not self.ntrip_client \
            and not self.is_in_bootloader \
            and not self.cli_options.use_cli:

            self.ntrip_rtcm_logf = open(os.path.join(self.rtk_log_file_name, 'rtcm_base_{0}.bin'.format(
                formatted_file_time)), "wb")

            thead = threading.Thread(target=self.ntrip_client_thread)
            thead.start()

        try:
            if (self.properties["initial"]["useDefaultUart"]):
                user_port_num, port_name = self.build_connected_serial_port_info()
                if not user_port_num or not port_name:
                    return False
                debug_port = port_name + \
                    str(int(user_port_num) + self.port_index_define['debug'])

            else:
                for x in self.properties["initial"]["uart"]:
                    if x['enable'] == 1:
                        if x['name'] == 'DEBUG':
                            debug_port = x["value"]

            self.user_logf = open(os.path.join(
                self.rtk_log_file_name, 'user_{0}.bin'.format(formatted_file_time)), "wb")

            self.rtcm_rover_logf = open(os.path.join(
                self.rtk_log_file_name, 'rtcm_rover1_{0}.bin'.format(formatted_file_time)), "wb")

            if debug_port != '':
                print_green('{0} log DEBUG UART {1}'.format(
                    self.device_category, debug_port))
                self.debug_serial_port = serial.Serial(
                    debug_port, '460800', timeout=0.1)
                if self.debug_serial_port.isOpen():
                    thead = threading.Thread(
                        target=self.thread_debug_port_receiver, args=(formatted_file_time,))
                    thead.start()

            self.save_device_info()
        except Exception as ex:
            if self.debug_serial_port is not None:
                if self.debug_serial_port.isOpen():
                    self.debug_serial_port.close()
            self.debug_serial_port = None
            APP_CONTEXT.get_logger().logger.error(ex)
            print_red(
                'Can not log GNSS UART or DEBUG UART, pls check uart driver and connection!')
            return False

    def on_read_raw(self, data):
        for bytedata in data:
            if bytedata == 0x24:
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
                            cksum, calc_cksum = self.nmea_checksum(
                                str_nmea)
                            if cksum == calc_cksum:
                                if str_nmea.find("$GPGGA") != -1 or str_nmea.find("$GNGGA") != -1:
                                    if self.ntrip_client:
                                        self.ntrip_client.send(str_nmea)
                                APP_CONTEXT.get_print_logger().info(str_nmea.replace('\r\n', ''))

                        except Exception as e:
                            pass
                    self.nmea_buffer = []
                    self.nmea_sync = 0


    def on_receive_output_packet(self, packet_type, data, *args, **kwargs):
        '''
        Listener for getting output packet
        '''
        if packet_type == 'rR':
            if self.rtcm_rover_logf:
                self.rtcm_rover_logf.write(bytes(data))
        else:
            raw_data = kwargs.get('raw')
            if self.user_logf and raw_data:
                self.user_logf.write(bytes(raw_data))

    # command list
    # use base methods
