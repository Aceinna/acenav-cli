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

Run the following command to log all data output from Ethernet port to binary files, setting a JSON format of configuration file and streaming GNSS RTK correction data through Ethernet port to INS401, then compared with JSON format of configuration files  of  “setting” folder and ins401_log_{time}" subfolder under "data" folder (e.g. on Ubuntu)
```shell
./acenav -i 100base-t1 -s
```
Run the following command to log all data output from Ethernet port to binary files, and streaming GNSS RTK correction data through Ethernet port to INS401 (e.g. on Ubuntu)

```shell
./acenav -i 100base-t1
```

A “data” subfolder will be created for the first time, and every session of data logging will be stored in a subfolder inside the “data” folder.

Run the following command to parse the logged data into text or csv files, 

```shell
./acenav parse -t ins401 -p <path to data folder/session data subfolder>
```

