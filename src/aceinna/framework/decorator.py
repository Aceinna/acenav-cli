import os
import sys
import argparse
import traceback
import signal
from datetime import datetime, timedelta
from functools import wraps
from typing import TypeVar
from .constants import (DEVICE_TYPES, INTERFACES)
from .utils.print import print_red
from .utils.resource import is_dev_mode


T = TypeVar('T')

INTERFACE_LIST = INTERFACES.list()
MODES = ['default', 'cli', 'receiver']
TYPES_OF_LOG = ['ins401']
KML_RATES = [1, 2, 5, 10]


def _build_args():
    """parse input arguments
    """
    parser = argparse.ArgumentParser(
        description='Aceinna python driver input args command:', allow_abbrev=False)

    parser.add_argument("-i", "--interface", dest="interface",  metavar='',
                        help="Interface. Allowed one of values: {0}".format(INTERFACE_LIST), default=INTERFACES.ETH_100BASE_T1, choices=INTERFACE_LIST)
    parser.add_argument("--cli", dest='use_cli', action='store_true',
                        help="start as cli mode", default=False)

    subparsers = parser.add_subparsers(
        title='Sub commands', help='use `<command> -h` to get sub command help', dest="sub_command")
    parse_log_action = subparsers.add_parser(
        'parse', help='A parse log command')
    parse_log_action.add_argument("-t", metavar='', type=str,
                                  help="Type of logs, Allowed one of values: {0}".format(
                                      TYPES_OF_LOG),
                                  default='ins401',  dest="log_type", choices=TYPES_OF_LOG)
    parse_log_action.add_argument(
        "-p", type=str, help="The folder path of logs", default='./data', metavar='', dest="path")
    return parser.parse_args()


def receive_args(func):
    '''
    build arguments in options
    '''
    @wraps(func)
    def decorated(*args, **kwargs):
        options = _build_args()
        kwargs['options'] = options
        func(*args, **kwargs)
    return decorated


def handle_application_exception(func):
    '''
    add exception handler
    '''
    @wraps(func)
    def decorated(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:  # response for KeyboardInterrupt such as Ctrl+C
            print('User stop this program by KeyboardInterrupt! File:[{0}], Line:[{1}]'.format(
                __file__, sys._getframe().f_lineno))
            os.kill(os.getpid(), signal.SIGTERM)
            sys.exit()
        except Exception as ex:  # pylint: disable=bare-except
            if is_dev_mode():
                traceback.print_exc()  # For development
            print_red('Application Exit Exception: {0}'.format(ex))
            os._exit(1)
    return decorated


def skip_error(T: type):
    '''
    add websocket error handler
    '''
    def outer(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except T:
                pass
        return decorated
    return outer


def throttle(seconds=0, minutes=0, hours=0):
    throttle_period = timedelta(seconds=seconds, minutes=minutes, hours=hours)

    def throttle_decorator(fn):
        time_of_last_call = datetime.min

        @wraps(fn)
        def wrapper(*args, **kwargs):
            nonlocal time_of_last_call
            now = datetime.now()
            if now - time_of_last_call > throttle_period:
                time_of_last_call = now
                return fn(*args, **kwargs)
        return wrapper
    return throttle_decorator
