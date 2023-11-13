import sys
import time
import struct
from ...framework.utils import (helper, resource)
from ...framework.context import APP_CONTEXT
from ...framework.utils.print import (print_red)

pG = [0x01, 0xcc]


def _run_command(communicator, command):
    run_command = helper.build_ethernet_packet(communicator.get_dst_mac(),
                                               communicator.get_src_mac(), command)
    communicator.reset_buffer()
    communicator.write(run_command.actual_command)

    time.sleep(0.1)
    data_buffer = helper.read_untils_have_data(
        communicator, command, retry_times=500)
    return data_buffer


def _format_string(data_buffer):
    parsed = bytearray(
        data_buffer) if data_buffer and len(data_buffer) > 0 else None

    formatted = ''
    if parsed is not None:
        try:
            if sys.version_info < (3, 0):
                formatted = str(
                    struct.pack('{0}B'.format(len(parsed)), *parsed))
            else:
                formatted = str(
                    struct.pack('{0}B'.format(len(parsed)), *parsed), 'utf-8')
        except UnicodeDecodeError:
            APP_CONTEXT.get_logger().logger.error(
                'Parse data as string failed')
            formatted = ''

    return formatted


def _need_check(limit_type, device_type):
    if limit_type is None:
        return True

    return limit_type == device_type


def run_command_as_string(communicator, command):
    ''' Run command and parse result as string
    '''
    data_buffer = _run_command(communicator, command)
    result = _format_string(data_buffer)

    return result


def try_parse_app_mode(device_type, info_text):
    is_app_mode = False
    app_ping_info = None

    split_text = info_text.split(' SN:')

    if len(split_text) == 1:
        split_text = info_text.split(' RTK_INS')
        is_app_mode = True

        device_info_text = split_text[0]
        app_info_text = 'RTK_INS' + split_text[1]

        app_ping_info = {
            'device_type': device_type,
            'device_info': device_info_text,
            'app_info': app_info_text
        }

    return is_app_mode, app_ping_info


def try_parse_bootloader_mode(device_type, info_text):
    is_bootloader_mode = False
    bootloader_ping_info = None

    split_text = info_text.split('SN:')
    if len(split_text) == 2:
        is_bootloader_mode = True

        device_info_text = info_text
        app_info_text = info_text

        bootloader_ping_info = {
            'device_type': device_type,
            'device_info': device_info_text,
            'app_info': app_info_text
        }

    return is_bootloader_mode, bootloader_ping_info


def ping(communicator, *args):
    '''OpenDevice Ping
    '''
    filter_device_type = args[0]

    cmd_info_text = run_command_as_string(communicator, pG)
    if cmd_info_text.find(',') > -1:
        info_text = cmd_info_text.replace(',', ' ')
    else:
        info_text = cmd_info_text

    # Prevent action. Get app info again,
    # if cannot retrieve any info at the first time of ping. Should find the root cause.

    if info_text.find(filter_device_type) > -1:
        is_app_mode, app_ping_info = try_parse_app_mode(filter_device_type, info_text)
        if is_app_mode:
            return app_ping_info

        is_bootloader_mode, bootloader_ping_info = try_parse_bootloader_mode(
            filter_device_type,
            info_text)
        if is_bootloader_mode:
            return bootloader_ping_info

        return None
    else:
        cmd_info = info_text.split(' ')
        if len(cmd_info) > 0:
            print_red('{0} != {1}'.format(filter_device_type, cmd_info[0]))
            print(info_text)

    return None
