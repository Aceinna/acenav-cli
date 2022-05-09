import struct
import threading
import time
import os
import datetime
import json
import sys
import collections
from queue import Queue
import subprocess
from ..models import WebserverArgs
from ..core.driver import (Driver, DriverEvents)
from ..core.device_context import DeviceContext

from ..framework.constants import APP_TYPE
from ..framework.context import APP_CONTEXT
from ..framework.utils import helper
from ..framework.decorator import throttle

from ..devices.widgets import(canfd, NTRIPClient, canfd_config)
from ..framework.utils import print as print_helper
from ..framework.utils import resource
from ..core.gnss import RTCMParser
import functools
import struct
from ..framework.utils.print import (print_green, print_yellow, print_red)

def with_device_message(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        generator_func = func(*args, **kwargs)
        global generator_result
        generator_result = None

        def check_result(message):
            message_version = list(message['data'])
            if(len(message) > 0):
                return message
        try:
            device_message = generator_func.send(None)
            return check_result(device_message)
        except Exception as e:
            print(e)
    return wrapper

def mkdir(file_path):
    if not os.path.exists(file_path):
        os.makedirs(file_path)
    return file_path

def get_utc_day():
	year = int(time.strftime("%Y"))
	month = int(time.strftime("%m"))
	day = int(time.strftime("%d"))
	hour = int(time.strftime("%H"))
	minute = int(time.strftime("%M"))
	second = int(time.strftime("%S"))
	local_time = datetime.datetime(year, month, day, hour, minute, second)
	time_struct = time.mktime(local_time.timetuple())
	utc_st = datetime.datetime.utcfromtimestamp(time_struct)
	
	d1 = datetime.datetime(year, 1, 1)
	utc_sub = utc_st - d1
	utc_str = utc_sub.__str__()
	utc_day_int = int(utc_str.split( )[0])
	utc_day_str = str(utc_day_int + 1)
	return utc_day_str

class canfd_app_driver:
    def __init__(self, **kwargs) -> None:
        self.cli_options = None
        self.fname_time = None
        self.device_info = None
        self.app_info = None
        self.base_count = 0
        self.properties = None
        self.rawdata = []
        self.pkfmt = {}
        self.remote_pkfmt = {}
        self.data_queue = Queue()
        self.id_name = {}
        self.log_files = {}
        self.rawdata_file = ''
        self.rover_file = ''
        self.imu_log = {}
        self.ins_log = {}
        self.all_base_len = 0
        self.valid_base_len = 0
        self._build_options(**kwargs)
        APP_CONTEXT.mode = APP_TYPE.CANFD
        day = get_utc_day()
        mkpath='./' + day
        self.path = mkdir(mkpath)
        self.load_properties()
        self.canfd_setting = self.properties["canfd_settings"]
        self.can_type = self.canfd_setting["canfd_type"]
        self.canfd_parse = self.canfd_setting['is_parse']

        self.can_id_list = None
        self.base_id = 0
        self.imu_log_title = None
        self.ins_log_title = None
        self.can_message_flag = 0
        self.can_imu_dict = {}
        self.can_ins_dict = {}
        self.ins_version_id = 0
        self.sta_version_id = 0
        self.imu_version_id = 0
        self.get_lever_arm_id = 0
        self.set_lever_arm_id = 0
        self.prepare_can_setting()
        self.prepare_log_config()
        args=[r"powershell",r"$Env:PYTHONPATH=\"./src/aceinna/devices/widgets;\"+$Env:PYTHONPATH"]
        p=subprocess.Popen(args, stdout=subprocess.PIPE)

    def setup(self, options):
        self.cli_options = options


    def prepare_log_config(self):
        self.fname_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
        self.imu_log_title = self.canfd_setting["imu_log_config"]["title"]
        self.ins_log_title = self.canfd_setting["ins_log_config"]["title"]

    def prepare_can_setting(self):
        if self.can_type == 'canfd':
            self.can_id_list = self.canfd_setting["canfd_id"]
            output = next((x for x in self.canfd_setting['canfd_messages'] if x['id'] == 640), None)
            self.set_lever_arm_id = next((x['id'] for x in self.canfd_setting['canfd_messages'] if x['name'] == 'LEVER_ARM_SET'), None)
        else:
            self.can_id_list = self.canfd_setting["can_id"]
            output = next((x for x in self.canfd_setting['can_messages'] if x['id'] == 640), None)
        self.valid_base_len = output["valid_len"]
        self.base_id = output["id"]
        for x in self.canfd_setting['canfd_remote_messages']:
            if x['name'] == 'INS_VERSION':
                self.ins_version_id = x['id']
            elif x['name'] == 'SDK_VERSION':
                self.sta_version_id = x['id']
            elif x['name'] == 'IMU_VERSION':
                self.imu_version_id = x['id']
            elif x['name'] == 'LEVER_ARM_GET':
                self.get_lever_arm_id = x['id']
        if self.can_type == 'canfd':
            for inode in self.canfd_setting['canfd_messages']:
                length = 0
                pack_fmt = '>'
                self.id_name[inode["id"]] = inode["name"]
                for value in inode['signals']:
                    if value['type'] == 'float':
                        pack_fmt += 'f'
                        length += 4
                    elif value['type'] == 'uint32':
                        pack_fmt += 'I'
                        length += 4
                    elif value['type'] == 'int32':
                        pack_fmt += 'i'
                        length += 4
                    elif value['type'] == 'int16':
                        pack_fmt += 'h'
                        length += 2
                    elif value['type'] == 'uint16':
                        pack_fmt += 'H'
                        length += 2
                    elif value['type'] == 'double':
                        pack_fmt += 'd'
                        length += 8
                    elif value['type'] == 'int64':
                        pack_fmt += 'q'
                        length += 8
                    elif value['type'] == 'uint64':
                        pack_fmt += 'Q'
                        length += 8
                    elif value['type'] == 'char':
                        pack_fmt += 'c'
                        length += 1
                    elif value['type'] == 'uchar':
                        pack_fmt += 'B'
                        length += 1
                    elif value['type'] == 'uint8':
                        pack_fmt += 'B'
                        length += 1
                    else:
                        pass
                len_fmt = '{0}B'.format(length)
                fmt_dic = collections.OrderedDict()
                fmt_dic['len'] = length
                fmt_dic['len_b'] = len_fmt
                fmt_dic['pack'] = pack_fmt
                self.pkfmt[inode['name']] = fmt_dic
            for inode in self.canfd_setting['canfd_remote_messages']:
                if(inode['valid_len'] > 0):
                    length = 0
                    pack_fmt = '<'
                    self.id_name[inode["id"]] = inode["name"]
                    for value in inode['signals']:
                        if value['type'] == 'float':
                            pack_fmt += 'f'
                            length += 4
                        elif value['type'] == 'uint32':
                            pack_fmt += 'I'
                            length += 4
                        elif value['type'] == 'int32':
                            pack_fmt += 'i'
                            length += 4
                        elif value['type'] == 'int16':
                            pack_fmt += 'h'
                            length += 2
                        elif value['type'] == 'uint16':
                            pack_fmt += 'H'
                            length += 2
                        elif value['type'] == 'double':
                            pack_fmt += 'd'
                            length += 8
                        elif value['type'] == 'int64':
                            pack_fmt += 'q'
                            length += 8
                        elif value['type'] == 'uint64':
                            pack_fmt += 'Q'
                            length += 8
                        elif value['type'] == 'char':
                            pack_fmt += 'c'
                            length += 1
                        elif value['type'] == 'uchar':
                            pack_fmt += 'B'
                            length += 1
                        elif value['type'] == 'uint8':
                            pack_fmt += 'B'
                            length += 1
                        else:
                            pass
                    len_fmt = '{0}B'.format(length)
                    fmt_dic = collections.OrderedDict()
                    fmt_dic['len'] = length
                    fmt_dic['len_b'] = len_fmt
                    fmt_dic['pack'] = pack_fmt
                    self.remote_pkfmt[inode['name']] = fmt_dic
                
        elif self.can_type == 'can':
            for inode in self.canfd_setting['can_messages']:
                length = 0
                pack_fmt = '>'
                self.id_name[inode["id"]] = inode["name"]
                for value in inode['signals']:
                    if value['type'] == 'float':
                        pack_fmt += 'f'
                        length += 4
                    elif value['type'] == 'uint32':
                        pack_fmt += 'I'
                        length += 4
                    elif value['type'] == 'int32':
                        pack_fmt += 'i'
                        length += 4
                    elif value['type'] == 'int16':
                        pack_fmt += 'h'
                        length += 2
                    elif value['type'] == 'uint16':
                        pack_fmt += 'H'
                        length += 2
                    elif value['type'] == 'double':
                        pack_fmt += 'd'
                        length += 8
                    elif value['type'] == 'int64':
                        pack_fmt += 'q'
                        length += 8
                    elif value['type'] == 'uint64':
                        pack_fmt += 'Q'
                        length += 8
                    elif value['type'] == 'char':
                        pack_fmt += 'c'
                        length += 1
                    elif value['type'] == 'uchar':
                        pack_fmt += 'B'
                        length += 1
                    elif value['type'] == 'uint8':
                        pack_fmt += 'B'
                        length += 1
                    else:
                        pass
                len_fmt = '{0}B'.format(length)
                fmt_dic = collections.OrderedDict()
                fmt_dic['len'] = length
                fmt_dic['len_b'] = len_fmt
                fmt_dic['pack'] = pack_fmt
                self.pkfmt[inode['name']] = fmt_dic


    def load_properties(self):
        local_config_file_path = os.path.join(
            os.getcwd(), 'setting/INS401/RTK_INS/ins401.json')
        setting_folder_path = 'setting/INS401/RTK_INS'
        if not os.path.isdir(setting_folder_path):
            os.makedirs(setting_folder_path)
        if not os.path.isfile(local_config_file_path):
            app_config_content = resource.get_content_from_bundle(
                'setting','INS401\\RTK_INS\\ins401.json')
            with open(local_config_file_path, "wb") as code:
                code.write(app_config_content)
        if os.path.isfile(local_config_file_path):
            with open(local_config_file_path) as json_data:
                self.properties = json.load(json_data)
                return
    def build_device_info(self, text):
        split_text = [x for x in text.split(' ') if x != '']
        sn = split_text[5]
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

    def build_app_info(self, text):
        '''
        Build app info
        '''
        app_version = text

        split_text = app_version.split(' ')

        if not app_name:
            app_name = 'INS'
            self.is_app_matched = False
        else:
            self.is_app_matched = True

        self.app_info = {
            'app_name': app_name,
            'version': text
        }

    def _build_device_info(self, ins_text, sta_text, imu_text):
        ins_split_text = [x for x in ins_text.split(' ') if x != '']
        sta_split_text = [x for x in sta_text.split(' ') if x != '']
        imu_split_text = [x for x in imu_text.split(' ') if x != '']
        sn = ins_split_text[0]
        if sn.find('SN:') == 0:
            sn = sn[3:]
        pn = ins_split_text[2]
        firmware_version = ins_split_text[3]
        boot = ins_split_text[5]
        imu = imu_split_text[2]
        sta = sta_split_text[2]

        self.device_info = {
            'name': 'INS401c',
            'sta': sta,
            'imu': imu,
            'pn': pn,
            'firmware_version': firmware_version,
            'sn': sn
        }
        version = 'RTK_INS App {0} Bootloader {1} IMU330ZA FW {2} STA9100 FW {3}'.format(
            firmware_version, boot, imu, sta
        )
        self.app_info = {
            'app_name': 'INS401c',
            "version": version
        }
    def get_lever_arm_dict(self, lever_arm_packet):
        parameters_configuration = dict()
        parameters_configuration['gnss lever arm x'] = lever_arm_packet[0]
        parameters_configuration['gnss lever arm y'] = lever_arm_packet[1]
        parameters_configuration['gnss lever arm z'] = lever_arm_packet[2]
        parameters_configuration['vrp lever arm x']  = lever_arm_packet[3]
        parameters_configuration['vrp lever arm y']  = lever_arm_packet[4]
        parameters_configuration['vrp lever arm z']  = lever_arm_packet[5]
        parameters_configuration['user lever arm x'] = lever_arm_packet[6]
        parameters_configuration['user lever arm y'] = lever_arm_packet[7]
        parameters_configuration['user lever arm z'] = lever_arm_packet[8]
        parameters_configuration['rotation rbvx']    = lever_arm_packet[9]
        parameters_configuration['rotation rbvy']    = lever_arm_packet[10]
        parameters_configuration['rotation rbvz']    = lever_arm_packet[11]
        return parameters_configuration

    def save_device_info(self):
        ins_result = (self.get_ins401c_message())
        time.sleep(0.1)
        sta_result = (self.get_sta_message())
        time.sleep(0.1)
        imu_result = self.get_imu_message()
        time.sleep(0.1)
        lever_arm_result = self.get_lever_arm_message()
        data = struct.pack(self.remote_pkfmt['LEVER_ARM_GET']['len_b'], *lever_arm_result['data'])
        lever_arm_packet = struct.unpack(self.remote_pkfmt['LEVER_ARM_GET']['pack'], data)
        device_configuration = None
        fname_time = self.fname_time + '_configuration.json'
        file_path = os.path.join(
            self.path, fname_time)

        if not os.path.exists(file_path):
            device_configuration = []
        else:
            with open(file_path) as json_data:
                device_configuration = (list)(json.load(json_data))

        if ins_result['id'] == self.ins_version_id:
            self._build_device_info(ins_result['data'].decode('utf-8').rstrip('\x00'),sta_result['data'].decode('utf-8').rstrip('\x00'), imu_result['data'].decode('utf-8').rstrip('\x00'))
            session_info = dict()
            session_info['time'] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime())
            session_info['device'] = self.device_info
            session_info['app'] = self.app_info
            print_green(self.app_info['version'])
            session_info['interface'] = 'canfd'
            parameters_configuration = self.get_lever_arm_dict(lever_arm_packet)
            session_info['parameters'] = parameters_configuration
            device_configuration.append(session_info)

            with open(file_path, 'w') as outfile:
                json.dump(device_configuration, outfile,
                          indent=4, ensure_ascii=False)


    def send_and_request(self, id, data, is_extended_id, is_fd, is_remote, time_out):
        self.canfd_handle.write(id, data, is_extended_id, is_fd, is_remote)
        time_over = float(time_out)/100 + time.time()
        result = {}
        result['id'] = id
        while True:
            msg = self.canfd_handle.read(timeout=0)
            if (msg is not None) and (msg.arbitration_id == id):
                result['data'] = msg.data
                result['error'] = None
                return result
            if(time.time() > time_over):
                result['error'] = 'time_out'
                return result
            

    @with_device_message
    def get_ins401c_message(self):
        result = yield self.send_and_request(self.ins_version_id, [0x00], False, False, True, 1000)
        data = result['data']
        error = result['error']
        if error == 'time_out':
            yield {
                'id': self.ins_version_id,
                'data': 'No Response'
            }

        if data:
            yield {
                'id': self.ins_version_id,
                'data': data
            }
    @with_device_message
    def get_sta_message(self):
        result = yield self.send_and_request(self.sta_version_id, [0x00], False, False, True, 1000)
        data = result['data']
        error = result['error']
        if error == 'time_out':
            yield {
                'id': 'error',
                'data': 'No Response'
            }

        if data:
            self.parameters = data
            yield {
                'id': 'None',
                'data': data
            }
    @with_device_message
    def get_imu_message(self):
        result = yield self.send_and_request(self.imu_version_id, [0x00], False, False, True, 1000)
        data = result['data']
        error = result['error']
        if error == 'time_out':
            yield {
                'id': 'error',
                'data': 'No Response'
            }

        if data:
            self.parameters = data
            yield {
                'id': 'None',
                'data': data
            }

    @with_device_message
    def get_lever_arm_message(self):
        result = yield self.send_and_request(self.get_lever_arm_id, [0x00], False, False, True, 1000)
        data = result['data']
        error = result['error']
        if error == 'time_out':
            yield {
                'id': 'error',
                'data': 'No Response'
            }

        if data:
            self.parameters = data
            yield {
                'id': 'None',
                'data': data
            }


    def set_ins401c_lever_arm(self, data):
        data_list = []
        for item in data:
            data_list.append(item["value"])
        para_len = self.pkfmt['LEVER_ARM_SET']['len'] / 4
        data_bytes = struct.pack('{0}f'.format(int(para_len)), *data_list)
        self.canfd_handle.write(self.set_lever_arm_id, list(data_bytes), False, False, True)

    def check_predefined_result(self):
        local_time = time.localtime()
        fname_time = self.fname_time + '_parameters_predefined.json'
        file_path = os.path.join(self.path, fname_time)
        # save parameters to data log folder after predefined parameters setup
        lever_arm_result = self.get_lever_arm_message()
        data = struct.pack(self.remote_pkfmt['LEVER_ARM_GET']['len_b'], *lever_arm_result['data'])
        lever_arm_packet = struct.unpack(self.remote_pkfmt['LEVER_ARM_GET']['pack'], data)
        parameters_configuration = self.get_lever_arm_dict(lever_arm_packet)
        with open(file_path, 'w') as outfile:
            json.dump(parameters_configuration, outfile)
        # compare saved parameters with predefined parameters
        hashed_predefined_parameters = helper.collection_to_dict(
            self.properties["initial"]["userParameters"], key='name')
        success_count = 0
        fail_count = 0
        fail_parameters = []
        for key in hashed_predefined_parameters:
            # if parameters_configuration[key] == \
            #         hashed_predefined_parameters[key]['value']:
            if abs(parameters_configuration[key] - hashed_predefined_parameters[key]['value'] < 0.1e5):
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
        return parameters_configuration
    
    def listen(self):
        self.prepare_driver()
        bustype= self.canfd_setting["can_config"]["bus_type"]
        channel= self.canfd_setting["can_config"]["channel"]
        bitrate= self.canfd_setting["can_config"]["bitrate"]
        data_bitrate= self.canfd_setting["can_config"]["data_bitrate"]
        while True:
            try:
                self.canfd_handle = canfd(canfd_config(bustype, channel, bitrate, data_bitrate))
                break
            except Exception as e:
                print_helper.print_on_console('CANFD:[open] open failed because: {0}'.format(e))
                time.sleep(5)
        
        print_helper.print_on_console('CANFD:[open] open BUSMUST CAN channel {0} using {1}&{2}kbps baudrate ...'.format(channel, bitrate, data_bitrate))
        print_helper.print_on_console('CANFD:[connect] waiting for receive CANFD messages ...')
        self.canfd_handle.canfd_bus_active()
        try_count = 5
        while try_count > 0:
            try:
                set_user_para = self.options.set_user_para
                if set_user_para:
                    result = self.set_ins401c_lever_arm(
                        self.properties["initial"]["userParameters"])
                    time.sleep(1)
                    result = self.check_predefined_result()
                    self.save_device_info()
                else:
                    self.save_device_info()
                try_count = 0
            except Exception as e:
                try_count-= 1
                time.sleep(1)
        self.start_parse()

    def ntrip_client_thread(self):
        self.ntrip_client = NTRIPClient(self.properties)
        self.ntrip_client.on('canfd_base', self.send_base_data)
        self.ntrip_client.run()

    def send_base_data(self, data):
        base_data = data
        all_data_len = len(base_data)
        len_base_data = all_data_len
        index = 0
        data_to_send = [0 for i in range(64)]
        while all_data_len > 0:
            if all_data_len < self.valid_base_len:
                data_len = len_base_data - index
                data_len_l = data_len & 0xff
                data_len_h = (data_len >> 8) & 0xff
                data_to_send[0:2] = [data_len_h, data_len_l]
                data_to_send[2:] = base_data[index:]
            else:
                data_len = self.valid_base_len
                data_len_l = data_len & 0xff
                data_len_h = (data_len >> 8) & 0xff
                data_to_send[0:2] = [data_len_h, data_len_l]
                data_to_send[2:] = base_data[index:index+self.valid_base_len]
            try:
                if self.can_type == 'canfd':
                    self.canfd_handle.write(self.base_id, data_to_send, False, False, True)
                elif self.can_type == 'can':
                    self.canfd_handle.write(self.base_id, data_to_send, False, False, False)
                    sys.stdout.write("\rsend base data len {0}".format(self.all_base_len))
            except Exception as e:
                print("message cant sent: ", e)
            all_data_len-= self.valid_base_len
            index+= self.valid_base_len
            self.all_base_len+= len_base_data
            sys.stdout.write("\rsend base data len {0}".format(self.all_base_len))

    def receive_parse_all(self):
        try:
            while True:
                msg = self.canfd_handle.read(timeout=0.01)
                if msg is not None:
                    self.data_queue.put(msg)
        except KeyboardInterrupt:
            pass

    def write_titlebar(self, file, output):
        for value in output['signals']:
            file.write(value['name']+'('+value['unit']+')')
            file.write(",")
        file.write("\n")

    def log(self, output, data):
        if output['name'] not in self.log_files.keys():
            fname_time = self.fname_time + '_'
            self.log_files[output['name']] = open(self.path + '/' + fname_time + output['name'] + '.csv', 'w')
            self.write_titlebar(self.log_files[output['name']], output)
            self.imu_log = open(self.path + '/' + fname_time + 'imu' + '.csv', 'w')
            self.ins_log = open(self.path + '/' + fname_time + 'ins' + '.csv', 'w')
            self.imu_log.write(self.imu_log_title)
            self.ins_log.write(self.ins_log_title)
        data_trans = []
        for i in range(len(data)):
            try:
                if output['signals'][i]['is_float'] == True:
                    offset = float(output['signals'][i]['offset'])
                    factor = float(output['signals'][i]['factor'])
                else:
                    offset = int(output['signals'][i]['offset'])
                    factor = int(output['signals'][i]['factor'])
            except Exception as e:
                print(e, output['is_float'], type(output['is_float']))
            data_trans.append(data[i]*factor + offset)
        buffer = ''
        imu_buffer = ''
        ins_buffer = ''
        if output['name'] == 'INSPVAX':
            buffer = buffer + format(data_trans[0]*9.7803267714, output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1]*9.7803267714, output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2]*9.7803267714, output['signals'][2]['format']) + ","
            buffer = buffer + format(data_trans[3], output['signals'][3]['format']) + ","
            buffer = buffer + format(data_trans[4], output['signals'][4]['format']) + ","
            buffer = buffer + format(data_trans[5], output['signals'][5]['format']) + ","
            buffer = buffer + format(data_trans[6], output['signals'][6]['format']) + ","
            buffer = buffer + format(data_trans[7], output['signals'][7]['format']) + ","
            buffer = buffer + format(data_trans[8], output['signals'][8]['format']) + ","
            buffer = buffer + format(data_trans[9], output['signals'][9]['format']) + ","
            buffer = buffer + format(data_trans[10], output['signals'][10]['format']) + ","
            buffer = buffer + format(data_trans[11], output['signals'][11]['format']) + ","
            buffer = buffer + format(data_trans[12], output['signals'][12]['format']) + ","
            buffer = buffer + format(data_trans[13], output['signals'][13]['format']) + ","
            buffer = buffer + format(data_trans[14], output['signals'][14]['format']) + ","
            buffer = buffer + format(data_trans[15], output['signals'][15]['format']) + ","
            buffer = buffer + format(data_trans[16], output['signals'][16]['format']) + ","            
            buffer = buffer + format(data_trans[17], output['signals'][17]['format']) + ","            
            buffer = buffer + format(data_trans[18], output['signals'][18]['format']) + ","            
            buffer = buffer + format(data_trans[19], output['signals'][19]['format']) + ","            
            buffer = buffer + format(data_trans[20], output['signals'][20]['format']) + ","            
            buffer = buffer + format(data_trans[21], output['signals'][21]['format']) + ","            
            buffer = buffer + format(data_trans[22], output['signals'][22]['format']) + ","
            buffer = buffer + format(data_trans[23], output['signals'][23]['format']) + ","
            buffer = buffer + format(data_trans[24], output['signals'][24]['format']) + ","
            buffer = buffer + format(data_trans[25], output['signals'][25]['format']) + ","
            buffer = buffer + format(data_trans[26], output['signals'][26]['format']) + ","
            buffer = buffer + format(data_trans[27] / 1000, output['signals'][27]['format']) + "\n"

            imu_buffer = imu_buffer + format(data_trans[26], output['signals'][26]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[27] / 1000, output['signals'][27]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[0]*9.7803267714, output['signals'][0]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[1]*9.7803267714, output['signals'][1]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[2]*9.7803267714, output['signals'][2]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[3], output['signals'][3]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[4], output['signals'][4]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[5], output['signals'][5]['format']) + ","
            imu_buffer = imu_buffer + format(data_trans[10], output['signals'][10]['format']) + "\n"

            ins_buffer = ins_buffer + format(data_trans[26], output['signals'][26]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[27] / 1000, output['signals'][27]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[20], output['signals'][20]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[21], output['signals'][21]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[11], output['signals'][11]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[12], output['signals'][12]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[9], output['signals'][9]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[13], output['signals'][13]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[14], output['signals'][14]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[15], output['signals'][15]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[7], output['signals'][7]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[6], output['signals'][6]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[8], output['signals'][8]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[22], output['signals'][22]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[23], output['signals'][23]['format']) + ","
            ins_buffer = ins_buffer + format(data_trans[24], output['signals'][24]['format']) + "\n"

        elif output['name'] == 'INS_ACC':
            if self.can_message_flag == 0:
                self.can_message_flag|= 0x01
                self.can_imu_dict['ACC_X'] = format(data_trans[0]*9.7803267714, output['signals'][0]['format'])
                self.can_imu_dict['ACC_Y'] = format(data_trans[1]*9.7803267714, output['signals'][1]['format'])
                self.can_imu_dict['ACC_Z'] = format(data_trans[2]*9.7803267714, output['signals'][2]['format'])
            buffer = buffer + format(data_trans[0]*9.7803267714, output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1]*9.7803267714, output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2]*9.7803267714, output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_GYRO':
            if self.can_message_flag == 0x01:
                self.can_message_flag|= 0x02
                self.can_imu_dict['GYRO_X'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['GYRO_Y'] = format(data_trans[1], output['signals'][1]['format'])
                self.can_imu_dict['GYRO_Z'] = format(data_trans[2], output['signals'][2]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_HeadingPitchRoll':
            if self.can_message_flag == 0x03:
                self.can_message_flag|= 0x04
                self.can_imu_dict['INS_PitchAngle'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['INS_RollAngle'] = format(data_trans[1], output['signals'][1]['format'])
                self.can_imu_dict['INS_HeadingAngle'] = format(data_trans[2], output['signals'][2]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_HeightAndIMUStatus':
            if self.can_message_flag == 0x07:
                self.can_message_flag|= 0x08
                self.can_imu_dict['INS_LocatHeight'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['IMU_Status'] = format(data_trans[1], output['signals'][1]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + "\n" 
        elif output['name'] == 'INS_LatitudeLongitude':
            if self.can_message_flag == 0x0f:
                self.can_message_flag|= 0x10
                self.can_imu_dict['INS_Latitude'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['INS_Longitude'] = format(data_trans[1], output['signals'][1]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + "\n" 
        elif output['name'] == 'INS_Speed':
            if self.can_message_flag == 0x1f:
                self.can_message_flag|= 0x20
                self.can_imu_dict['INS_NorthSpd'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['INS_EastSpd'] = format(data_trans[1], output['signals'][1]['format'])
                self.can_imu_dict['INS_ToGroundSpd'] = format(data_trans[2], output['signals'][2]['format'])                
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_DataInfo':
            if self.can_message_flag == 0x3f:
                self.can_message_flag|= 0x40
                self.can_imu_dict['INS_GpsFlag_Pos'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['INS_NumSV'] = format(data_trans[1], output['signals'][1]['format'])
                self.can_imu_dict['INS_GpsFlag_Heading'] = format(data_trans[2], output['signals'][2]['format'])
                self.can_imu_dict['INS_Gps_Age'] = format(data_trans[3], output['signals'][3]['format'])
                self.can_imu_dict['INS_Car_Status'] = format(data_trans[4], output['signals'][4]['format'])
                self.can_imu_dict['INS_Status'] = format(data_trans[5], output['signals'][5]['format']) 
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + ","
            buffer = buffer + format(data_trans[3], output['signals'][3]['format']) + ","
            buffer = buffer + format(data_trans[4], output['signals'][4]['format']) + ","
            buffer = buffer + format(data_trans[5], output['signals'][5]['format']) + "\n" 
        elif output['name'] == 'INS_Std':
            if self.can_message_flag == 0x7f:
                self.can_message_flag|= 0x80
                self.can_imu_dict['INS_Std_Lat'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['INS_Std_Lon'] = format(data_trans[1], output['signals'][1]['format'])
                self.can_imu_dict['INS_Std_LocatHeight'] = format(data_trans[2], output['signals'][2]['format'])
                self.can_imu_dict['INS_Std_Heading'] = format(data_trans[3], output['signals'][3]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + ","            
            buffer = buffer + format(data_trans[3], output['signals'][3]['format']) + "\n" 
        elif output['name'] == 'INS_Time':
            if self.can_message_flag == 0xff:
                self.can_message_flag|= 0x100
                self.can_imu_dict['Week'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_imu_dict['TimeOfWeek'] = format(float(data_trans[1])/1000, output['signals'][1]['format'])
                self.can_ins_dict['Week'] = format(data_trans[0], output['signals'][0]['format'])
                self.can_ins_dict['TimeOfWeek'] = format(float(data_trans[1])/1000, output['signals'][1]['format'])
            else:
                self.can_message_flag = 0
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(float(data_trans[1])/1000, output['signals'][1]['format']) + "\n"
        if self.can_message_flag == 0x1ff:
            self.can_message_flag = 0
            imu_buffer = imu_buffer + self.can_imu_dict['Week'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['TimeOfWeek'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['ACC_X'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['ACC_Y'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['ACC_Z'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['GYRO_X'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['GYRO_Y'] + ','
            imu_buffer = imu_buffer + self.can_imu_dict['GYRO_Z'] + '\n'
            ins_buffer = ins_buffer + self.can_imu_dict['Week'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['TimeOfWeek'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Car_Status'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Status'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Latitude'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Longitude'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_LocatHeight'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_NorthSpd'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_EastSpd'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_ToGroundSpd'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_RollAngle'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_PitchAngle'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_HeadingAngle'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Std_Lat'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Std_Lon'] + ','
            ins_buffer = ins_buffer + self.can_imu_dict['INS_Std_LocatHeight'] + '\n'
            self.can_imu_dict = {}
            self.can_ins_dict = {}
        self.log_files[output['name']].write(buffer)
        if(len(imu_buffer) > 0):
            self.imu_log.write(imu_buffer)
        if(len(ins_buffer) > 0):
            self.ins_log.write(ins_buffer)

    def openrtk_unpack_output_packet(self, output, payload):
        fmt = self.pkfmt[output['name']]
        len_fmt = fmt['len_b']
        pack_fmt = fmt['pack']
        try:
            b = struct.pack(len_fmt, *payload)
            data = struct.unpack(pack_fmt, b)
            self.log(output, data)
        except Exception as e:
            print("error happened when decode the {0} {1}".format(output['name'], e))

    def parse_output_packet_payload(self, can_id, data):
        if self.can_type == 'canfd':
            output = next((x for x in self.canfd_setting['canfd_messages'] if x['id'] == can_id), None)
        elif self.can_type == 'can':
            output = next((x for x in self.canfd_setting['can_messages'] if x['id'] == can_id), None)
        if output != None:
            valid_len = output["valid_len"]
            data_hex = [hex(ele) for ele in data]
            if output["name"] != 'ROVER_RTCM':
                if self.canfd_parse == True:
                    self.openrtk_unpack_output_packet(output, data[0:valid_len])
            else:
                self.rover_file.write(data[1:valid_len+1])
        else:
            pass

    def start_parse(self):
        fname_time = self.fname_time + '_'
        self.rawdata_file = open(self.path + '/' + fname_time + 'canfd.txt', 'w')
        self.rover_file = open(self.path + '/' + fname_time + 'rover.bin', 'wb')
        thread = threading.Thread(target=self.receive_parse_all)
        thread.start()
        thead = threading.Thread(target=self.ntrip_client_thread)
        thead.start()
        # self.canfd_id = self.canfd_setting['canfd_id']

        while True:
            if self.data_queue.empty():
                time.sleep(0.001)
                continue
            else:
                '''
                'arbitration_id', 'bitrate_switch', 'channel', 'data', 'dlc', 'equals', 
                'error_state_indicator', 'id_type', 'is_error_frame', 'is_extended_id', 
                'is_fd', 'is_remote_frame', 'timestamp
                '''
                data = self.data_queue.get()
                if data.arbitration_id in self.can_id_list:
                    try:
                        self.rawdata_file.write(str(data)+'\n')
                    except Exception as e:
                        print(e)
                    self.parse_output_packet_payload(data.arbitration_id, data.data)

    def _build_options(self, **kwargs):
        self.options = WebserverArgs(**kwargs)

    def prepare_driver(self):
        self.prepare_folder()

    def prepare_folder(self):
        executor_path = resource.get_executor_path()
        lib_folder_name = 'libs'

        # copy contents of setting file under executor path
        lib_folder_path = os.path.join(
            executor_path, lib_folder_name)

        if not os.path.isdir(lib_folder_path):
            os.makedirs(lib_folder_path)

        platform = sys.platform

        if platform.startswith('win'):
            lib_file = 'BMAPI64.dll'

        lib_path = os.path.join(lib_folder_path, lib_file)

        if not os.path.isfile(lib_path):
            lib_content = resource.get_content_from_bundle(
                lib_folder_name, lib_file)
            if lib_content is None:
                raise ValueError('Lib file content is empty')
            with open(lib_path, "wb") as code:
                code.write(lib_content)
        return True



