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
        self.properties = None
        self.rawdata = []
        self.pkfmt = {}
        self.data_queue = Queue()
        self.id_name = {}
        self.log_files = {}
        self.rawdata_file = ''
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
        self.can_id_list = None
        self.prepare_can_setting()
        self.base_id = 0x508
        args=[r"powershell",r"$Env:PYTHONPATH=\"./src/aceinna/devices/widgets;\"+$Env:PYTHONPATH"]
        p=subprocess.Popen(args, stdout=subprocess.PIPE)

    def prepare_can_setting(self):
        if self.can_type == 'canfd':
            self.can_id_list = self.canfd_setting["canfd_id"]
            output = next((x for x in self.canfd_setting['canfd_messages'] if x['id'] == 640), None)
        else:
            self.can_id_list = self.canfd_setting["can_id"]
            output = next((x for x in self.canfd_setting['can_messages'] if x['id'] == 640), None)
        self.valid_base_len = output["valid_len"]        

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

    def listen(self):
        self.prepare_driver()
        bustype= self.canfd_setting["can_config"]["bus_type"]
        channel= self.canfd_setting["can_config"]["channel"]
        bitrate= self.canfd_setting["can_config"]["bitrate"]
        data_bitrate= self.canfd_setting["can_config"]["data_bitrate"]
        self.canfd_handle = canfd(canfd_config(bustype, channel, bitrate, data_bitrate))
        print_helper.print_on_console('CANFD:[open] open BUSMUST CAN channel {0} using {1}&{2}kbps baudrate ...'.format(channel, bitrate, data_bitrate))
        print_helper.print_on_console('CANFD:[connect] waiting for receive CANFD messages ...')
        self.canfd_handle.canfd_bus_active()
        self.start_pasre()

    def ntrip_client_thread(self):
        self.ntrip_client = NTRIPClient(self.properties)
        self.ntrip_client.on('canfd_base', self.send_base_data)
        self.ntrip_client.run()

    def send_base_data(self, data):
        base_data = list(data)
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
                    self.canfd_handle.write(self.base_id, data_to_send, False, True)
            except Exception as e:
                print("message cant sent: ", e)
            pass
            all_data_len-= self.valid_base_len
            index+= self.valid_base_len
            self.all_base_len+= len_base_data
            sys.stdout.write("\rsend base data len {0}".format(self.all_base_len))

    def receive_parse_all(self):
        try:
            while True:
                msg = self.canfd_handle.read(timeout=0.1)
                if msg is not None:
                    self.data_queue.put(msg)
        except KeyboardInterrupt:
            pass

    def write_titlebar(self, file, output):
        for value in output['signals']:
            #print(value['name']+'('+value['unit']+')')
            file.write(value['name']+'('+value['unit']+')')
            file.write(",")
        file.write("\n")

    def log(self, output, data):
        if output['name'] not in self.log_files.keys():
            fname_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()) + '_'
            self.log_files[output['name']] = open(self.path + '/' + fname_time + output['name'] + '.csv', 'w')
            self.write_titlebar(self.log_files[output['name']], output)
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

        #print(len(output['signals']), len(data_trans), len(data))
        buffer = ''
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
            buffer = buffer + format(data_trans[25], output['signals'][25]['format']) + "\n"              
        elif output['name'] == 'INS_ACC':
            buffer = buffer + format(data_trans[0]*9.7803267714, output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1]*9.7803267714, output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2]*9.7803267714, output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_GYRO':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_HeadingPitchRoll':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_HeightAndTime':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + "\n" 
        elif output['name'] == 'INS_LatitudeLongitude':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + "\n" 
        elif output['name'] == 'INS_Speed':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + "\n" 
        elif output['name'] == 'INS_DataInfo':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + ","
            buffer = buffer + format(data_trans[3], output['signals'][3]['format']) + ","
            buffer = buffer + format(data_trans[4], output['signals'][4]['format']) + ","
            buffer = buffer + format(data_trans[5], output['signals'][5]['format']) + "\n" 
        elif output['name'] == 'INS_Std':
            buffer = buffer + format(data_trans[0], output['signals'][0]['format']) + ","
            buffer = buffer + format(data_trans[1], output['signals'][1]['format']) + ","
            buffer = buffer + format(data_trans[2], output['signals'][2]['format']) + ","            
            buffer = buffer + format(data_trans[3], output['signals'][3]['format']) + "\n" 
        self.log_files[output['name']].write(buffer)

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
            
            self.openrtk_unpack_output_packet(output, data[0:valid_len])
        else:
            pass

    def start_pasre(self):
        fname_time = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()) + '_'
        self.rawdata_file = open(self.path + '/' + fname_time + '.txt', 'w')
        thread = threading.Thread(target=self.receive_parse_all)
        thread.start()
        thead = threading.Thread(target=self.ntrip_client_thread)
        thead.start()
        # self.canfd_id = self.canfd_setting['canfd_id']
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



