Simple ANT-BMS parser for BLE16ZNUB.
With small modifications it could also parse all other ANT-BMS devices.

Code does everything for you. Scans for devices, connects, restarts module on errors, parses and prints data.
Tested on Rasberry PI and up to 33 devices. A full scan of 33 devices with 3 BLE requests per device takes about 1 minute.

In some cases the BlueTooth module in the PI4 hangs and seems to only be fixed by a reboot. When this happens 0 devices are found.
