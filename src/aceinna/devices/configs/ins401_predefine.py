"""
predefined params for openrtk
"""


def get_ins401_products():
    return {
        'INS401':['RTK_INS']
    }


def get_configuratin_file_mapping():
    return {
        'INS401':'ins401.json'
    }


def get_ins402_products():
    return {
        'INS402':['RTK_INS']
    }


def get_ins402_configuratin_file_mapping():
    return {
        'INS402':'ins402.json'
    }

def get_ins502_products():
    return {
        'INS502':['RTK_INS']
    }


def get_ins502_configuratin_file_mapping():
    return {
        'INS502':'ins502.json'
    }

APP_STR = ['RAWDATA', 'RTK', 'RTK_INS', 'RTK_INS_CANFD']
