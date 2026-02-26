Simple ANT-BMS parser for BLE16ZNUB.
With small modifications it could also parse all other ANT-BMS devices.

Code does everything for you. Scans for devices, connects, restarts module on errors, parses and prints data.
Tested on Rasberry PI and up to 33 devices. A full scan of 33 devices with 3 BLE requests per device takes about 1 minute.
Scans never end and keep on going indefinitely. Results are compressed into max/min results, mos status, and which BMS name per value.
```
temp  max:7.0 - ANT-BLE16ZNUB-KHP2  min:2.0 - ANT-BLE16ZNUB-4558  avg:4.2
tot_v  max:46.27 - ANT-BLE16ZNUB-XDTA  min:46.15 - ANT-BLE16ZNUB-897Q  avg:46.22
amp  max:-2.2 - ANT-BLE16ZNUB-7TR4  min:-5.0 - ANT-BLE16ZNUB-4558  avg:-3.12
dchg_mos  dchg_mos:['All On']
chg_mos  chg_mos:['All On']
cur_ah  max:47.1 - ANT-BLE16ZNUB-4558  min:25.0 - ANT-BLE16ZNUB-7TR4  avg:30.98
dv_cell  max:0.017 - ANT-BLE16ZNUB-6947  min:0.002 - ANT-BLE16ZNUB-9ESL  avg:0.01
avg_v  max:3.856 - ANT-BLE16ZNUB-XDTA  min:3.846 - ANT-BLE16ZNUB-897Q  avg:3.85
Found 33 devices
Loop 01:43:06
```

Negative current means charging.

In some cases the BlueTooth module in the PI4 hangs and seems to only be fixed by a reboot. When this happens 0 devices are found.
