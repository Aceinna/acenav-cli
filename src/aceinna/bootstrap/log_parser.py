import os
import sys
from ctypes import *
from ..models import LogParserArgs
from ..framework.constants import APP_TYPE
from ..framework.context import APP_CONTEXT
from ..framework.utils import resource

def prepare_lib_folder():
    executor_path = resource.get_executor_path()
    lib_folder_name = 'libs'

    # copy contents of setting file under executor path
    lib_folder_path = os.path.join(
        executor_path, lib_folder_name)

    if not os.path.isdir(lib_folder_path):
        os.makedirs(lib_folder_path)

    platform = sys.platform

    if platform.startswith('win'):
        lib_file = 'UserDecoderLib.dll'
    if platform.startswith('linux'):
        lib_file = 'UserDecoderLib.so'

    lib_path = os.path.join(lib_folder_path, lib_file)

    if not os.path.isfile(lib_path):
        lib_content = resource.get_content_from_bundle(
            lib_folder_name, lib_file)
        if lib_content is None:
            raise ValueError('Lib file content is empty')

        with open(lib_path, "wb") as code:
            code.write(lib_content)

    return lib_path


def do_parse(log_type, folder_path, kml_rate, dr_parse):
    lib_path = prepare_lib_folder()

    lib = CDLL(lib_path)
    for root, _, file_name in os.walk(folder_path):
        for fname in file_name:
            if (fname.startswith('user') and fname.endswith('.bin')) or (fname.startswith('ins_save') and fname.endswith('.bin')) or ('canfd' in fname and fname.endswith('.txt')):
                file_path = os.path.join(folder_path, fname)
                if log_type == 'rtkl':
                    lib.decode_openrtk_inceptio(bytes(file_path, encoding='utf8'))
                elif log_type == 'beidou':
                    lib.decode_beidou(bytes(file_path, encoding='utf8'), kml_rate)
                elif log_type == 'ins401' or log_type == 'ins402':
                    lib.decode_ins401(bytes(file_path, encoding='utf8'), bytes(dr_parse, encoding='utf8'), kml_rate)
                elif log_type == 'ins401c':
                    lib.decode_ins401c(bytes(file_path, encoding='utf8'))
                elif log_type == 'rtk350la':
                    lib.decode_rtk350la(bytes(file_path, encoding='utf8'))
                elif log_type == 'ins502':
                    lib.decode_ins502(bytes(file_path, encoding='utf8'))


class LogParser:
    _options = None
    _tunnel = None
    _driver = None

    def __init__(self, **kwargs):
        self._build_options(**kwargs)
        APP_CONTEXT.mode = APP_TYPE.DEFAULT

    def listen(self):
        '''Start to do parse
        '''
        self._validate_params()

        do_parse(self._options.log_type,
                 self._options.path,
                 self._options.kml_rate,
                 self._options.powerdr)

        os._exit(1)

    def _validate_params(self):
        for attr_name in ['log_type', 'path', 'kml_rate', 'powerdr']:
            attr_value = getattr(self._options, attr_name)
            if not attr_value:
                raise ValueError(
                    'Parameter {0} should have a value'.format(attr_name))

    def _build_options(self, **options):
        self._options = LogParserArgs(**options)
