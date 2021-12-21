import os
import time
import sys


def get_list_from_int(value):
	value_list = [0 for x in range(0, 4)]
	value_list[0] = value & 0xff
	value_list[1] = (value >> 8) & 0xff
	value_list[2] = (value >> 16) & 0xff
	value_list[3] = (value >> 24) & 0xff
	return value_list
	
def fill_to_16(value):
    value_all = list(value)
    data_len_remain = len(value) % 16
    print(data_len_remain)
    if(data_len_remain != 0):
        for i in range(16 - data_len_remain):
            value_all.insert(len(value_all), 0xff)
    return bytes(value_all)

def file_combine(file_ins, file_all):
    fs_ins = open(file_ins,'rb')
    fs_all = open(file_all,'wb')

    ins_data = fs_ins.read()
    ins_data_fill = fill_to_16(ins_data)
    ins_size = len(ins_data_fill)
    ins_size_list = []
    ins_size_list = get_list_from_int(ins_size)
    
    fs_all.write(b'ins_start:')
    fs_all.write(bytes(ins_size_list))
    fs_all.write(ins_data_fill)	
    
    
if __name__ == '__main__':
	print(sys.argv[1])
	print(sys.argv[2])
	file_combine(sys.argv[1],sys.argv[2])

	