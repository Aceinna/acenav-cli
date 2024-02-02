# CHANGELOG

---
## 2.6.12， 02/02/2024
- [INS502] Resolve ping packet(0xcc01) parse issue.

## 2.6.11， 12/06/2023
- [RTK350LA] Optimized the RTK350LA rtcm log naming.

## 2.6.10， 11/13/2023
- [INS502] Support INS502 data logging.

## 2.6.9， 10/04/2023
- [RTK350LA] Support to decode RTK350LA output data.

## 2.6.8， 09/28/2023
- [INS402] Support algorithm parameters configuration in cli mode.

## 2.6.7， 02/15/2023
- [INS402] Add ins402 parse command
- [INS401] Add parameter configuration type to be filtered to resolve timeout issue
- [INS401C] modify canfd setings, add can_id 0x181 0x282
- [INS401C] set lever format issue
- [INS401] log corrimu data
- [INS401] Add FreeRTOS of ins firmware, after upgrade sta9100 SDK firmware, GPGGA fixed type is RTK_FLOAT
- [INS401C] print ins401c serial number
- [INS401] print ins and gnss lib version
- [INS401] modify ins401c gyro unit
- [INS402] add antenna switch enable(default value: 0) for INS402 8100 double antenna version
- [INS402] add dual ant cali config
- [INS402C] update canfd protocol
- [INS402C] enable log id: 0x181, 0x282
- [INS402C] modify .json file: modify canfd and can factor and unit of sigal GYRO_X GYRO_Y GYRO_Z, 0.0076293 to 0.00762951, unit s to deg/s
- [INS401/INS402]Add set ins401 and ins402 unit serial number command, ".\acenav.exe -i 100base-t1 -sn XXXXXX" or ".\acenav.exe -i 100base-t1 --device-type INS402 -sn XXXXXX"
- [INS402C] Update User DecoderLib

## 2.6.6， 09/23/2022

- [INS401] The reply message 0xcc01 can't be received after the "JS" command is executed.
- [INS401] GPZDA messages are saved to log, compatible with Sta9100 and Mosaic.
- [INS401] optimized the firmware upgradation function and ethernet connection
- [INS401] Support Sta9100 upgradation of the new bootloader and is compatible with the old bootloader.
- [INS401] filter invalid MAC address
- [INS401] Updated the function of obtaining the botloader version number
- [INS401] Ping messages are compatible with old and new versions with different delimiters
- [INS401] Ethernet cache queue increases
- [INS401] rtk and ins firmware upgrade, erase flash delay time update
- [INS401] After imu boot upgradation, the IMU fails to switch to boot because the baud rate of the IMU serial port 
is changed.
- [INS401] The default firmware upgrades include RTK, INS, and STA9100 SDK.
- [INS401] The sta9100 upgrade improve
- [INS401] optimized the problem which is getting ins401 configuration parameters messages timeout
- [INS401] update the delay for jumping to the bootloader during the upgraded firmware
- [INS401C] canfd python env issue and canfd set lever issue
- [BEIDOU] modify beidou config file, add binary commands
- [BEIDOU] log unico raw data and update beidou.json
- [INS401] Ethernet cache queue increases
- [INS401] Updated the function of obtaining the botloader version number
- [INS401] optimized the problem which is getting ins401 configuration parameters messages timeout
- [INS401] update the delay for jumping to the bootloader during the upgraded firmware
- [INS401] After Failed to send the IMU "JI" command occasionally, add system reset, Ethernet reconnection, and IMU "JI" command resend functions
- [INS401] Supports multiple Spaces and TAB keys to separate firmware upgrade commands
- [INS401] modify ins401.json file: change offset of INS_PitchAngle  INS_RollAngle INS_HeadingAngle to -360 from -250
- [INS402] support ins402 firmware fully upgrade, contains a default list  of the modules which are  rtk, ins, sdk and sdk_2.
- [INS402] support the firmware upgrade of a single optional module
- [INS402] Add ins402 NHC switch parameter configuration
- [INS402] Optimized the sta9100 firmware upgrade
- [INS401] fix other bugs

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

