import collections
import operator
import time
import struct
from ..base.message_parser_base import MessageParserBase
from ...framework.utils import helper
from ...framework.context import APP_CONTEXT
from .ins401_packet_parser import (
    match_command_handler, common_continuous_parser, other_output_parser)

MSG_HEADER = [0x55, 0x55]
PACKET_TYPE_INDEX = 2
PACKET_PAYLOAD_LEN_INDEX = 4
PACKET_PAYLOAD_INDEX = 8

INPUT_PACKETS = [b'\x01\xcc', b'\x02\xcc', b'\x03\xcc', b'\x04\xcc', b'\x05\xcc',b'\x06\xcc', 
                 b'\x01\x0b', b'\x02\x0b', b'\x09\x0a', b'\x09\xaa', b'\x01\xfc']
                 
OTHER_OUTPUT_PACKETS = [b'\x01\n', b'\x02\n', b'\x03\n', b'\x04\n', b'\x05\n', b'\x06\n', b'\x08\n',b'\x09\x0a', b'\x0a\x0a', b'\x0b\x0a', b'\x0c\x0a', 
                        b'\x07\n', b'\x09\xaa', b'\x44\x4D', b'\x49\x67', b'\x64\x66']


class EthernetMessageParser(MessageParserBase):
    def __init__(self, configuration):
        super(EthernetMessageParser, self).__init__(configuration)

    def set_run_command(self, command):
        pass

    def analyse(self, data_block):
        if operator.eq(list(data_block[0:2]), MSG_HEADER) and len(data_block) >= PACKET_PAYLOAD_INDEX:
            payload_len_byte = bytes(data_block[PACKET_PAYLOAD_LEN_INDEX:PACKET_PAYLOAD_INDEX])
            payload_len = struct.unpack('<I', payload_len_byte)[0]
   
            packet_type_byte = bytes(data_block[PACKET_TYPE_INDEX:PACKET_PAYLOAD_LEN_INDEX])
            packet_type = struct.unpack('>H', packet_type_byte)[0]

            if len(data_block) < PACKET_PAYLOAD_INDEX + payload_len + 2:
                APP_CONTEXT.get_logger().logger.info(
                    "crc check error! packet_type:{0}".format(packet_type))

                self.emit('crc_failure', packet_type=packet_type,
                            event_time=time.time())
                print('crc_failure', packet_type=packet_type,
                            event_time=time.time())
                return

            result = helper.calc_crc(data_block[PACKET_TYPE_INDEX:PACKET_PAYLOAD_INDEX+payload_len])
                
            if result[0] == data_block[PACKET_PAYLOAD_INDEX + payload_len] and result[1] == data_block[PACKET_PAYLOAD_INDEX + payload_len + 1]:
                self._parse_message(
                    struct.pack('>H', packet_type), payload_len, data_block)
            else:
                APP_CONTEXT.get_logger().logger.info(
                    "crc check error! packet_type:{0}".format(packet_type))

                self.emit('crc_failure', packet_type=packet_type,
                            event_time=time.time())
                input_packet_config = next(
                    (x for x in self.properties['userMessages']['inputPackets']
                        if x['name'] == packet_type), None)
                if input_packet_config:
                    self.emit('command',
                                packet_type=packet_type,
                                data=[],
                                error=True,
                                raw=data_block)

    def _parse_message(self, packet_type, payload_len, frame):
        payload = frame[PACKET_PAYLOAD_INDEX:payload_len+PACKET_PAYLOAD_INDEX]
        # parse interactive commands
        is_interactive_cmd = INPUT_PACKETS.__contains__(packet_type)

        if is_interactive_cmd:
            self._parse_input_packet(packet_type, payload, frame)
        else:
            # consider as output packet, parse output Messages
            self._parse_output_packet(packet_type, payload, frame)

    def _parse_input_packet(self, packet_type, payload, frame):
        payload_parser = match_command_handler(packet_type)

        if payload_parser:
            data, error = payload_parser(
                payload, self.properties['userConfiguration'])
            self.emit('command',
                      packet_type=packet_type,
                      data=data,
                      error=error,
                      raw=frame)
        else:
            print('[Warning] Unsupported command {0}'.format(
                packet_type.encode()))

    def _parse_output_packet(self, packet_type, payload, frame):
        # check if it is the valid out packet
        payload_parser = None
        is_other_output_packet = OTHER_OUTPUT_PACKETS.__contains__(packet_type)
        if is_other_output_packet:
            payload_parser = other_output_parser
            data = payload_parser(payload)

            self.emit('continuous_message',
                      packet_type=packet_type,
                      data=payload,
                      event_time=time.time(),
                      raw=frame)
            return

        payload_parser = common_continuous_parser

        output_packet_config = next(
            (x for x in self.properties['userMessages']['outputPackets']
                if x['name'] == packet_type), None)
        data = payload_parser(payload, output_packet_config)

        if not data:
            # APP_CONTEXT.get_logger().logger.info(
            #     'Cannot parse packet type {0}. It may caused by firmware upgrade'.format(packet_type))
            return

        self.emit('continuous_message',
                  packet_type=packet_type,
                  data=data,
                  event_time=time.time())
