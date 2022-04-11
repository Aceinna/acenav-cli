"""
Helper
"""
import struct
import sys
import collections
import time
from .dict_extend import Dict
from ..constants import INTERFACES
from ..command import Command

if sys.version_info[0] > 2:
    from queue import Queue
else:
    from Queue import Queue

COMMAND_START = [0x55, 0x55]
PACKET_FOUND_INIT_STATE = 0
PACKET_FOUND_START_STATE = 1
PACKET_FOUND_TYPE_STATE = 2
PACKET_FOUND_LENGTH_STATE = 3
PACKET_FOUND_PAYLOAD_STATE = 4

crc16_table = [0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0]

def build_packet(message_type, message_bytes=[]):
    '''
    Build final packet
    '''
    packet = []
    packet.extend(bytearray(message_type, 'utf-8'))

    msg_len = len(message_bytes)
    packet.append(msg_len)
    final_packet = packet + message_bytes
    # print(message_type, final_packet)
    return COMMAND_START + final_packet + calc_crc(final_packet)


def build_ethernet_packet(dest, src, message_type, message_bytes=[], payload_length_format='<I', use_length_as_protocol=True, *args, **kwargs):
    '''
    Build ethernet packet
    '''
    packet = []
    packet.extend(message_type)
    msg_len = len(message_bytes)

    packet_len = struct.pack(payload_length_format, msg_len)

    packet.extend(packet_len)
    final_packet = packet + message_bytes

    payload_len = len(COMMAND_START) + len(final_packet) + 2

    if not use_length_as_protocol:
        payload_len = 0

    payload_len_in_short = struct.pack('<H', payload_len)

    whole_packet = []
    header = dest + src + payload_len_in_short
    whole_packet.extend(header)

    whole_packet.extend(COMMAND_START)
    whole_packet.extend(final_packet)
    whole_packet.extend(calc_crc(final_packet))
    if payload_len < 46:
        fill_bytes = bytes(46-payload_len)
        whole_packet.extend(fill_bytes)

    return Command(message_type, bytes(whole_packet), payload_length_format)


def build_input_packet(name, properties=None, param=False, value=False):
    '''
    Build input packet
    '''
    packet = []

    if not param and not value:
        packet = build_packet(name)
    else:
        payload = unpack_payload(name, properties, param, value)
        packet = build_packet(name, payload)
    return packet


def build_bootloader_input_packet(name, data_len=False, addr=False, data=False):
    '''
    Build bootloader input packet
    '''
    if not data_len and not addr and not data:
        packet = build_packet(name)
    else:
        payload = block_payload(data_len, addr, data)
        packet = build_packet(name, payload)
    return packet


def build_read_eeprom_input_packet(start, word_len):
    '''
    Build RE command
    '''
    payload = []
    payload.append((start & 0xFF00) >> 8)
    payload.append(start & 0x00FF)
    payload.append(word_len)
    packet = build_packet('RE', payload)
    return packet


def build_write_eeprom_input_packet(start, word_len, data):
    '''
    Build WE command
    '''
    name_bytes = list(struct.unpack('BB', bytearray('WE', 'utf-8')))
    payload = []
    payload.append((start & 0xFF00) >> 8)
    payload.append(start & 0x00FF)
    payload.append(word_len)
    payload.extend(data)
    command = COMMAND_START + name_bytes + [word_len*2+3] + payload
    packet = command + calc_crc(command[2:command[4]+5])
    return packet


def build_unlock_eeprom_packet(sn):
    '''
    Build UE command
    '''
    sn_crc = calc_crc(sn)
    payload = sn_crc
    packet = build_packet('UE', payload)
    return packet


def build_lock_eeprom_packet():
    '''
    Build UE command
    '''
    packet = build_packet('LE')
    return packet


def unpack_payload(name, properties, param=False, value=False):
    '''
    Unpack payload
    '''
    input_packet = next(
        (x for x in properties['userMessages']['inputPackets'] if x['name'] == name), None)

    if name == 'ma':
        input_action = next(
            (x for x in input_packet['inputPayload'] if x['actionName'] == param), None)
        return [input_action['actionID']]
    elif input_packet is not None:
        if input_packet['inputPayload']['type'] == 'paramId':
            return list(struct.unpack("4B", struct.pack("<L", param)))
        elif input_packet['inputPayload']['type'] == 'userParameter':
            payload = list(struct.unpack("4B", struct.pack("<L", param)))
            if properties['userConfiguration'][param]['type'] == 'uint64':
                payload += list(struct.unpack("8B", struct.pack("<Q", value)))
            elif properties['userConfiguration'][param]['type'] == 'int64':
                payload += list(struct.unpack("8B", struct.pack("<q", value)))
            elif properties['userConfiguration'][param]['type'] == 'double':
                payload += list(struct.unpack("8B",
                                              struct.pack("<d", float(value))))
            elif properties['userConfiguration'][param]['type'] == 'uint32':
                payload += list(struct.unpack("4B", struct.pack("<I", value)))
            elif properties['userConfiguration'][param]['type'] == 'int32':
                payload += list(struct.unpack("4B", struct.pack("<i", value)))
            elif properties['userConfiguration'][param]['type'] == 'float':
                payload += list(struct.unpack("4B", struct.pack("<f", value)))
            elif properties['userConfiguration'][param]['type'] == 'uint16':
                payload += list(struct.unpack("2B", struct.pack("<H", value)))
            elif properties['userConfiguration'][param]['type'] == 'int16':
                payload += list(struct.unpack("2B", struct.pack("<h", value)))
            elif properties['userConfiguration'][param]['type'] == 'uint8':
                payload += list(struct.unpack("1B", struct.pack("<B", value)))
            elif properties['userConfiguration'][param]['type'] == 'int8':
                payload += list(struct.unpack("1B", struct.pack("<b", value)))
            elif 'char' in properties['userConfiguration'][param]['type']:
                c_len = int(properties['userConfiguration']
                            [param]['type'].replace('char', ''))
                if isinstance(value, int):
                    length = len(str(value))
                    payload += list(struct.unpack('{0}B'.format(length),
                                                  bytearray(str(value), 'utf-8')))
                else:
                    length = len(value)
                    payload += list(struct.unpack('{0}B'.format(length),
                                                  bytearray(value, 'utf-8')))
                for i in range(c_len-length):
                    payload += [0x00]
            elif properties['userConfiguration'][param]['type'] == 'ip4':
                ip_address = value.split('.')
                ip_address_v4 = list(map(int, ip_address))
                for i in range(4):
                    payload += list(struct.unpack("1B",
                                                  struct.pack("<B", ip_address_v4[i])))
            elif properties['userConfiguration'][param]['type'] == 'ip6':
                ip_address = value.split('.')
                payload += list(struct.unpack('6B',
                                              bytearray(ip_address, 'utf-8')))

            return payload


def block_payload(data_len, addr, data):
    '''
    Block payload
    '''
    data_bytes = []
    addr_3 = (addr & 0xFF000000) >> 24
    addr_2 = (addr & 0x00FF0000) >> 16
    addr_1 = (addr & 0x0000FF00) >> 8
    addr_0 = (addr & 0x000000FF)
    data_bytes.insert(len(data_bytes), addr_3)
    data_bytes.insert(len(data_bytes), addr_2)
    data_bytes.insert(len(data_bytes), addr_1)
    data_bytes.insert(len(data_bytes), addr_0)
    data_bytes.insert(len(data_bytes), data_len)
    for i in range(data_len):
        if sys.version_info > (3, 0):
            data_bytes.insert(len(data_bytes), data[i])
        else:
            data_bytes.insert(len(data_bytes), ord(data[i]))
    return data_bytes


def parse_command_packet(raw_command):
    packet_type = ''
    payload = []
    error = False

    raw_command_start = raw_command[0:2]
    raw_packet_type = raw_command[2:4]

    if COMMAND_START == raw_command_start:
        packet_type = bytes(raw_packet_type).decode()
        payload_len = raw_command[4]  # struct.unpack('b', data[4])[0]
        payload = raw_command[5:payload_len+5]
    else:
        error = True

    return packet_type, payload, error


def calc_crc(payload):
    '''
    Calculates 16-bit CRC-CCITT
    '''
    crc = 0x1D0F
    for bytedata in payload:
        crc = crc ^ (bytedata << 8)
        i = 0
        while i < 8:
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            i += 1

    crc = crc & 0xffff
    crc_msb = (crc & 0xFF00) >> 8
    crc_lsb = (crc & 0x00FF)
    return [crc_msb, crc_lsb]

def calc_crc16_quick(payload):
    crc = 0x1D0F
    print(len(payload))
    for bytedata in payload:
        crc = (crc16_table[((crc >> 8) ^ bytedata) & 0xFF] ^ (crc << 8)) & 0xFFFF
        
    return [(crc>>8) & 0xff, crc & 0xff]

def clear_elements(list_instance):
    '''
    clear list
    '''
    if sys.version_info < (3, 0):
        list_instance[:] = []
    else:
        list_instance.clear()


def dict_to_object(dict_obj):
    '''
    Convert Dict to Object
    '''
    if not isinstance(dict_obj, dict):
        return dict_obj
    inst = Dict()
    for key, val in dict_obj.items():
        inst[key] = dict_to_object(val)
    return inst


def name_convert_camel_to_snake(camel_name):
    '''
    Convert Camel naming to snake case
    '''
    chars = []
    underscore = '_'

    lower_camel_name = camel_name.lower()

    for i, char in enumerate(camel_name):
        add_underscore = False
        lower_char = lower_camel_name[i]
        if char != lower_char:
            add_underscore = True if i > 0 else False

        if add_underscore:
            chars.append(underscore+lower_char)
        else:
            chars.append(lower_char)

    return ''.join(chars)


def _parse_buffer(data_buffer):
    response = {
        'parsed': False,
        'parsed_end_index': 0,
        'result': []
    }
    data_queue = Queue()
    data_queue.queue.extend(data_buffer)

    command_start = [0x55, 0x55]
    parsed_data = []
    is_header_found = False
    packet_type = ''
    data_buffer_len = len(data_buffer)

    while not data_queue.empty():
        if is_header_found:
            # if matched packet, is_header_found = False, parsed_data = []
            if not data_queue.empty():
                packet_type_start = data_queue.get()
            else:
                break

            if not data_queue.empty():
                packet_type_end = data_queue.get()
            else:
                break

            if not data_queue.empty():
                packet_len = data_queue.get()
                packet_type = ''.join(
                    ["%c" % x for x in [packet_type_start, packet_type_end]])
                packet_data = []

                if data_queue.qsize() >= packet_len:
                    # take packet
                    for _ in range(packet_len):
                        packet_data.append(data_queue.get())
                else:
                    break
                # update response
                response['parsed'] = True
                response['result'].append({
                    'type': packet_type,
                    'data': packet_data
                })
                response['parsed_end_index'] += data_buffer_len - \
                    data_queue.qsize()
                data_buffer_len = data_queue.qsize()
                parsed_data = []
                is_header_found = False
            else:
                break
        else:
            byte_item = data_queue.get()
            parsed_data.append(byte_item)

            if len(parsed_data) > 2:
                parsed_data = parsed_data[-2:]

            if parsed_data == command_start:
                # find message start
                is_header_found = True
                parsed_data = []

    return response

def _parse_eth_100base_t1_buffer(data_buffer):
    response = {
        'parsed': False,
        'parsed_end_index': len(data_buffer),
        'result': []
    }

    command_start = [0x55, 0x55]
    PAYLOAD_INDEX = 8
    PAYLOAD_LEN_INDEX = 4
    PACKET_TYPE_INDEX = 2
    packet_type = []
    
    if list(data_buffer[0:2]) == command_start and len(data_buffer) >= PAYLOAD_INDEX:
        payload_len_byte = bytes(data_buffer[PAYLOAD_LEN_INDEX:PAYLOAD_INDEX])
        payload_len = struct.unpack('<I', payload_len_byte)[0]

        packet_type = data_buffer[PACKET_TYPE_INDEX:PAYLOAD_LEN_INDEX]
 
        if len(data_buffer) >= PAYLOAD_INDEX + payload_len + 2:
            crc = calc_crc(data_buffer[2:8+payload_len])   

            if crc[0] == data_buffer[PAYLOAD_INDEX + payload_len] and crc[1] == data_buffer[PAYLOAD_INDEX + payload_len + 1]:
                response['parsed'] = True
                response['result'].append({
                    'type': packet_type,
                    'data': data_buffer[PAYLOAD_INDEX:PAYLOAD_INDEX + payload_len]
                })

    return response

def read_untils_have_data(communicator,
                          packet_type,
                          read_length=200,
                          retry_times=20,
                          payload_length_format='<I'):
    '''
    Get data from limit times of read
    '''
    result = None
    trys = 0
    data_buffer = []

    while trys < retry_times:
        read_data = communicator.read(read_length)
        time.sleep(0.001)
        if read_data is None:
            trys += 1
            continue

        data_buffer_per_time = bytearray(read_data)
        data_buffer.extend(data_buffer_per_time)
        if hasattr(communicator, 'type') and communicator.type == INTERFACES.ETH_100BASE_T1:
            response = _parse_eth_100base_t1_buffer(data_buffer)
        else:
            response = _parse_buffer(data_buffer)

        if response['parsed']:
            matched_packet = next(
                (packet['data'] for packet in response['result']
                 if packet['type'] == packet_type), None)
            if matched_packet is not None:
                result = matched_packet
            else:
                # clear buffer to parsed index
                data_buffer = data_buffer[response['parsed_end_index']:]

        if result is not None:
            break

        trys += 1

    return result


def collection_to_dict(collection, key):
    '''
    Convet a collection to dict
    '''
    inst = dict()
    for item in collection:
        actual_key = item[key]
        inst[actual_key] = item
    return inst


def format_firmware_content(content):
    len_mod = len(content) % 16
    if len_mod == 0:
        return content

    fill_bytes = bytes(16-len_mod)

    return content + fill_bytes
