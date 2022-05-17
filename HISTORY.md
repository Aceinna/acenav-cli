# CHANGELOG

---
## 2.6.6， 05/17/2022
- [INS401] The reply message 0xcc01 can't be received after the "JS" command is executed.
- [INS401] GPZDA messages are saved to log, compatible with Sta9100 and Mosaic.
- [INS401] optimized the firmware upgradation function and ethernet connection

## 2.6.5， 04/11/2022
- [INS401] Support firmware upgrade after completion, automatically connect and log
- [INS401] After the IMU firmware is upgraded, the IMU is displayed in the bootloader, the solution is system (including IMU) reset of ins401 Unit
- [INS401] The serial port baud rate of STA9100 SDK firmware upgraded is compatible with 230400bps and 115200, which is distinguished by  the firmware version of the 0xcc01 message
- [INS401] The Ethernet ack packet of the ins401 unit is shorter than 64 bytes, QNX os cannot receive ack packet, causing firmware upgradding failure.

## 2.6.4， 03/16/2022

- [INS401] Add gnss solution interity packet is saved to log file
- [INS401] STA9100 SDK upgrading default baud rate is 115200bps and upgrading steps are modified
- [INS401] Add IMU bootloader upgrading function
- [INS401] Support one or more modules of firmware(rtk, ins, sdk, imu_boot and imu) can be upgraded via ethernet
- [INS401] Support the upgrading packet length is 960 by new bootloader and 192 bytes for old bootloader
- [INS401] STA9100 SDK upgrading bug fix

## 2.6.3， 12/20/2021

- [INS401] Support GPGGA and GNGGA message of NMEA format
- [INS401] Add ethernet Ping message to automatically discover devices
- [INS401] Distinguish between bootloader and app through SN
- [INS401] IMU upgrade bug

## 2.6.2， 10/25/2021

- [INS401] Support real time installation angle estimation
- [INS401] Support dead reckoning right after power up before GNSS fix
- [RTK330LA] Add RTK330LA driver



## 2.6.1,  09/03/2021

- [INS401] Support FW IAP upgrade through 100base-t1 Ethernet interface

- [INS401] Bug fix

  

## 2.6.0，08/19/2021

- [INS401] Add the Ethernet driver for INS401 device, supports data logging on a PC using a 100base-TX to 100base-T1 converter
- [INS401,RTK330LA] New code developments based on OpenRTK Python driver 2.5.0

