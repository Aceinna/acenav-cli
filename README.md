# ACENAV CLI 

The “AceNav” is a Command Line Interface (CLI) software runs on user computers, to connect and interact with Aceinna GNSS/INS navigation devices for user parameter settings, GNSS RTK correction streaming from a NTRIP server, and output data logging and parsing.

## System requirement

Ubuntu 18.04:

​      Python 3.7

​      Lib: tcpdump, https://scapy.readthedocs.io/en/latest/installation.html#debian-ubuntu-fedora

 

Windows 10:

​      Python 3.7

​      Lib: npcap, https://scapy.readthedocs.io/en/latest/installation.html#windows

 

Mac:

​      Python 3.7

​      Lib: libpcap, https://scapy.readthedocs.io/en/latest/installation.html#mac-os-x 



## GNSS/INS operation user settings

Run the CLI software and connect with the INS401 system for the first time, there is a “setting” folder generated with subfolders named by Aceinna GNSS/INS navigation devices. Each type of device has a JSON format of configuration file, all the user settings including GNSS RTK correction NTRIP account information, IMU to GNSS antenna lever arm and so on. User must modify the related configurations/settings to achieve effective GNSS/INS operation. For example, user should change the NTRIP settings (IP address, port, mount point, account, and password) to accessible GNSS correction service.

## Commands

#### Log data

Run the following command to log all data output from Ethernet port to binary files, and streaming GNSS RTK correction data through Ethernet port to INS401 (e.g. on Ubuntu)

```shell
./acenav -i 100base-t1
```

A “data” subfolder will be created for the first time, and every session of data logging will be stored in a subfolder inside the “data” folder.

#### Parse Data

Run the following command to parse the logged data into text or csv files, 

```shell
./acenav parse -t ins401 -p <path to data folder/session data subfolder>
```

#### Save Settings

If user changed the GNSS/INS user settings in the "ins401.json" file, and wants to make it effective, run the data logging command with "-s" option like below, and the changed user settings will be saved into flash

```shell
./acenav -i 100base-t1 -s
```

## Firmware Upgrade

INS401 supports In-Application Programming (IAP) firmware upgrade through the Ethernet interface, run the executable with the CLI option, and prompt for user input 

```shell
./acenav -i 100base-t1 --cli
# console display with connection information
# prompt for user input, type in command and file path after the arrow symbol
# firmware is fully upgraded by default
>>upgrade <INS401 FW file path>

# one or more firmware parts(rtk, ins, sdk, imu_boot(if firmware is merged), imu) 
# are optionally upgraded
>>upgrade <INS401 FW file path> rtk ins sdk
or
>>upgrade <INS401 FW file path> sdk
or
>>upgrade <INS401 FW file path> imu_boot imu
```

After successful FW upgrade, the INS401 system restarts and starts logging data automatically. 

## canfd app  
please run $Env:PYTHONPATH="./src/aceinna/devices/widgets;"+$Env:PYTHONPATH in powershell  
to set env:PYTHONPATH then  
```shell cmd
./acenav -i canfd
```
or run acenav-cli whit run_with_bat.bat  
