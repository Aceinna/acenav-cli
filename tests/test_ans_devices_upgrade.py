import subprocess
from threading import Thread 
import time
import sys
import signal
import os
import platform
import argparse


def build_args():
    parser = argparse.ArgumentParser(
        description='Aceinna python driver input args command:', allow_abbrev=False)

    parser.add_argument("-a", "--app", dest="app")
    parser.add_argument("-b", "--bin", dest='bin')
    return parser.parse_args()


args = build_args()
print(args)

test_platform = platform.system().lower()
if platform.system().lower() == 'windows':
    print("windows")
elif platform.system().lower() == 'linux':
    print("linux")


suc_count = 0
fail_count = 0
all_count = 0

while True:
    print('start')
    out_file = 'stdout_{0}.txt'.format(all_count)
    f_w = open(out_file,'wb')
    time.sleep(5)
    if test_platform == 'windows':
        x=subprocess.Popen(['powershell', '{0} --cli'.format(args.app)], stdin=subprocess.PIPE, stdout=f_w,close_fds=True)
        x.stdin.write(bytes('upgrade {0}\r\n'.format(args.bin),encoding='utf-8'))
    else:
        x=subprocess.Popen(["{0}".format(args.app), "--cli"], stdin=subprocess.PIPE, stdout=f_w)
        x.stdin.write(bytes('upgrade {0}\n'.format(args.bin),encoding='utf-8'))    
    x.stdin.flush()

    while True:
        fr = open(out_file,'r')
        data = fr.read()
        if len(data) == 0:
            time.sleep(1)
            continue
        else:
            if('100.00%' in data):
                time.sleep(10)
                suc_count+= 1
                all_count+= 1
                f_w.close()
                x.stdin.close()
                #x.kill()
                if test_platform == 'windows':
                    os.system('taskkill /im ans-devices.exe /f')
                else:
                    os.system('killall ans-devices')                
                print('suc count = {0}, fail count = {1}'.format(suc_count,fail_count))
                time.sleep(10)
                break
            elif('failed' in data):
                fail_count+= 1
                all_count+= 1
                f_w.close()
                x.stdin.close()
                #x.kill()
                if test_platform == 'windows':
                    os.system('taskkill /im ans-devices.exe /f')
                else:
                    os.system('killall ans-devices')     
                print('suc count = {0}, fail count = {1}'.format(suc_count,fail_count))
                time.sleep(10)
                break
        time.sleep(1)
        fr.close()
            
