import struct


def parse_data_len(data_len):
    '''Parse data length
    '''
    return struct.unpack('<L', data_len)[0]

def parse_str(content, current_pos, len):
    for i in range(len):
        if content[current_pos + i] == 0x3A:
            part_start_str = bytes.decode(content[current_pos: current_pos + i + 1])
            return part_start_str

def parser(content, parser_rules):
    ''' content is a bytes like input
    '''
    current_pos = 0
    parsed_content = {}

    for rule in parser_rules:
        if parse_str(content, current_pos, len(rule.start_str)) == rule.start_str:
            part_start_str_pos = current_pos + len(rule.start_str)
            part_data_len_pos = part_start_str_pos + rule.data_len_count

            part_data_len = parse_data_len(content[part_start_str_pos: part_data_len_pos])
            part_data_end_pos = part_data_len_pos + part_data_len
            parsed_content[rule.name] = content[part_data_len_pos: part_data_end_pos]
            current_pos = part_data_end_pos
        else:
            parsed_content[rule.name] = b''

    return parsed_content
