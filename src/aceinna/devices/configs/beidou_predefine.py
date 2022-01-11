"""
predefined params for openrtk
"""


def get_beidou_products():
    return {
        'beidou': ['ins']
    }


def get_app_names():
    '''
    define app type
    '''
    app_names = ['BEIDOU']
    return app_names


def get_configuratin_file_mapping():
    return {
        'beidou': 'beidou.json'
    }


APP_STR = ['INS']
