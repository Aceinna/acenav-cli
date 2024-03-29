"""
predefined params for openrtk 
"""


def get_rtk_products():
    return {
        'RTK330L': ['RTK_INS'],
        'RTK350L': ['RTK_INS']
    }


def get_app_names():
    '''
    define openimu app type
    '''
    app_names = ['RTK_INS']
    return app_names


def get_configuratin_file_mapping():
    return {
        'RTK330L': 'RTK330L.json',
        'RTK350L': 'RTK350LA.json'
    }


APP_STR = ['RTK_INS']
