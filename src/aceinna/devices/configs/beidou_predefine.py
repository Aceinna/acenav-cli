"""
predefined params for openrtk
"""


def get_beidou_products():
    return {
        'beidou': ['INS']
    }


def get_app_names():
    '''
    define app type
    '''
    app_names = ['INS']
    return app_names


def get_configuratin_file_mapping():
    return {
        'beidou': 'beidou.json'
    }


APP_STR = ['INS']
