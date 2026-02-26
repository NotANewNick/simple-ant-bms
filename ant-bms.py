import argparse
import asyncio
import contextlib
import logging
from typing import Iterable
from datetime import datetime
from colorama import Fore, Back, Style
import os
import platform
import time
import struct

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

global bledata
bledata = {}

COMMAND = bytes.fromhex("7E A1 01 00 00 BE 18 55 AA 55")
FRAME_START = b'\x7E'
FRAME_END = b'\xAA\x55'

buffers = {}
found_devices = ["",]


async def connect_to_device(
	lock: asyncio.Lock,
	by_address: bool,
	macos_use_bdaddr: bool,
	name_or_address: str,
	dname: str,
	notify_uuid: str,
	idx: int,
	):
	"""
	Scan and connect to a device then print notifications for 10 seconds before
	disconnecting.

	Args:
	lock:
	    The same lock must be passed to all calls to this function.
	by_address:
	    If true, treat *name_or_address* as an address, otherwise treat
	    it as a name.
	macos_use_bdaddr:
	    If true, enable hack to allow use of Bluetooth address instead of
	    UUID on macOS.
	name_or_address:
	    The Bluetooth address/UUID of the device to connect to.
	notify_uuid:
	    The UUID of a characteristic that supports notifications.
	"""
	logging.info("starting %s task", dname)

	try:
		async with contextlib.AsyncExitStack() as stack:

		    # Trying to establish a connection to two devices at the same time
		    # can cause errors, so use a lock to avoid this.
			async with lock:
				logging.info("scanning for %s", dname)
				
				if by_address:
				    device = await BleakScanner.find_device_by_address(
					str(name_or_address), cb={"use_bdaddr": macos_use_bdaddr}
				    )
				else:
				    device = await BleakScanner.find_device_by_name(str(name_or_address))
				
				logging.info("stopped scanning for %s", dname)

				if device is None:
				    logging.error("%s not found", dname)
				    return
				
				logging.info("connecting to %s", dname)
				try:
					client = await stack.enter_async_context(BleakClient(device))

					logging.info("connected to %s", dname)

					# This will be called immediately before client.__aexit__ when
					# the stack context manager exits.
					stack.callback(logging.info, "disconnecting from %s", dname)
				except:
					print("", end="")


		    # The lock is released here. The device is still connected and the
		    # Bluetooth adapter is now free to scan and connect another device
		    # without disconnecting this one.

			def parse_bms_frame(data: bytes, device: str):
				#Parse ANT BMS status frame (function 0x11)
				# Status code lookup tables  
				CHARGE_MOSFET_STATUS = [  
					"Off", "On", "Overcharge protection", "Over current protection",  
					"Battery full", "Total overpressure", "Battery over temperature",  
					"MOSFET over temperature", "Abnormal current", "Balanced line dropped string",  
					"Motherboard over temperature", "Unknown", "Unknown",  
					"Discharge MOSFET abnormality", "Unknown", "Manually turned off", "other1", "Cold Protect", "other3", "other4", "other5"
				]  
				  
				DISCHARGE_MOSFET_STATUS = [  
					"Off", "On", "Overdischarge protection", "Over current protection",  
					"Unknown", "Total pressure undervoltage", "Battery over temperature",  
					"MOSFET over temperature", "Abnormal current", "Balanced line dropped string",  
					"Motherboard over temperature", "Charge MOSFET on", "Short circuit protection",  
					"Discharge MOSFET abnormality", "Start exception", "Manually turned off" , "other1", "Cold Protect", "other3", "other4", "other5"
				]  
				  
				BALANCER_STATUS = [  
					"Off", "Exceeds the limit equilibrium", "Charge differential pressure balance",  
					"Balanced over temperature", "Automatic equalization", "Unknown",  
					"Unknown", "Unknown", "Unknown", "Unknown", "Motherboard over temperature"  
				]
				BATTERY_STATUS = [  
					"Unknown",      # 0x00  
					"Idle",         # 0x01  
					"Charge",       # 0x02  
					"Discharge",    # 0x03  
					"Standby",      # 0x04  
					"Error",        # 0x05  
				] 
				#global bledata
				# Helper functions for little-endian byte extraction  
				def get_16bit(i):  
					return (data[i + 1] << 8) | data[i + 0]  
				  
				def get_32bit(i):  
					return (get_16bit(i + 2) << 16) | get_16bit(i + 0)  

				def get_64bit(i):  
					"""Extract 64-bit little-endian integer"""  
					return (get_32bit(i + 4) << 32) | get_32bit(i + 0)    				  
					
				# Validate frame length
				try:  
					if len(data) != (6 + data[5] + 4):  
						print(f"Invalid frame length ", ' '.join(f'{b:02x}' for b in data)) 
						return None
				except:
					print(f"Invalid frame length ", ' '.join(f'{b:02x}' for b in data)) 
					return None
				
				bledata[idx] = {}
				
				bledata[idx]['name'] = dname

				offset = data[9] * 2  
				  
				# Parse temperature sensors (dynamic length)  
				bledata[idx]['temp'] = []  
				for i in range(data[8]):  
					# Signed 16-bit integer  
					temp_raw = get_16bit(i * 2 + 34 + offset)  
					temp = temp_raw if temp_raw < 32768 else temp_raw - 65536  
					bledata[idx]['temp'].append(float(temp))  
				  
				offset += data[8] * 2  
				  
				# MOSFET temperature  
				mosfet_temp_raw = get_16bit(34 + offset)  
				#result['mosfet_temperature'] = mosfet_temp_raw if mosfet_temp_raw < 32768 else mosfet_temp_raw - 65536  
				  
				# Balancer temperature  
				balancer_temp_raw = get_16bit(36 + offset)  
				#result['balancer_temperature'] = balancer_temp_raw if balancer_temp_raw < 32768 else balancer_temp_raw - 65536  
				  
				# Total voltage  
				bledata[idx]['tot_v'] = round(get_16bit(38 + offset) * 0.01,2)
				  
				# Current (signed)  
				current_raw = get_16bit(40 + offset)  
				bledata[idx]['amp'] = round((current_raw if current_raw < 32768 else current_raw - 65536) * 0.1, 1)
				  
				# State of charge  
				#result['soc'] = get_16bit(42 + offset) * 1.0  
				  
				# State of health  
				#result['soh'] = get_16bit(44 + offset) * 1.0  
				  
				# MOSFET status codes  
				bledata[idx]['dchg_mos'] = DISCHARGE_MOSFET_STATUS[data[46 + offset]]
				bledata[idx]['chg_mos'] = CHARGE_MOSFET_STATUS[data[47 + offset]]
				#result['balancer_status'] = BALANCER_STATUS[data[48 + offset]]
				  
				# Reserved byte at 49 + offset  
				  
				# Battery capacity (32-bit)  
				#result['total_battery_capacity'] = round(get_32bit(50 + offset) * 0.000001,2)
				  
				# Remaining capacity  
				bledata[idx]['cur_ah'] = round(get_32bit(54 + offset) * 0.000001,1)
				  
				# Battery cycle capacity  
				#result['battery_cycle_capacity'] = round(get_32bit(58 + offset) * 0.001,2)
				  
				# Power (signed 32-bit)  
				power_raw = get_32bit(62 + offset)  
				#result['power'] = power_raw if power_raw < 2147483648 else power_raw - 4294967296  
				  
				# Total runtime (seconds)  
				#result['total_runtime'] = get_32bit(66 + offset)  
				  
				# Balanced cell bitmask  
				#result['balanced_cell_bitmask'] = get_32bit(70 + offset)  

				# Cell voltage statistics (lines 386-425)  
				#result['max_cell_voltage'] = round(get_16bit(74 + offset) * 0.001,3)
				#result['max_voltage_cell'] = get_16bit(76 + offset) * 1.0  
				#result['min_cell_voltage'] = round(get_16bit(78 + offset) * 0.001,3)
				#result['min_voltage_cell'] = get_16bit(80 + offset) * 1.0  
				bledata[idx]['dv_cell'] = round(get_16bit(82 + offset) * 0.001,3)
				bledata[idx]['avg_v'] = round(get_16bit(84 + offset) * 0.001,3)
				  
				# Additional metrics (logged but not stored in sensors)  
				#result['accumulated_discharging_capacity'] = get_32bit(96 + offset) * 0.001  # Ah  
				#result['accumulated_charging_capacity'] = get_32bit(100 + offset) * 0.001    # Ah  
				#result['accumulated_discharging_time'] = get_32bit(104 + offset)             # seconds  
				#result['accumulated_charging_time'] = get_32bit(108 + offset) 
				warning_bitmask = get_64bit(18)  
				binary_str = f"{warning_bitmask:064b}"  
				formatted = ' '.join([binary_str[i:i+8] for i in range(0, 64, 8)])  
				#print(f"Warning bitmask (formatted): {formatted}") 
				
				#print("Device: ", end="")
				#print(dname, end="")
				#print(f": Warningbit: {formatted} ", end="")
				#print(bledata[idx])
				parsed = True
				return


				
			def extract_frames(buffer: bytearray):
				"""Extracts complete ANT BMS frames from the buffer."""
				frames = []
				while True:
					start = buffer.find(FRAME_START)
					if start == -1:
						break
					end = buffer.find(FRAME_END, start)
					if end == -1:
						break
					frame = buffer[start:end + len(FRAME_END)]
					frames.append(frame)
					del buffer[:end + len(FRAME_END)]
				return frames
				
			def callback(_: BleakGATTCharacteristic, data: bytearray) -> None:
				key = (name_or_address, str(BleakGATTCharacteristic)) 
				buffer = buffers.setdefault(key, bytearray())
				buffer += data

				#print(f"? [{device_address}] Received chunk: {data.hex().upper()}")

				# Try to extract full frames
				for frame in extract_frames(buffer):
				    #print(f"\n? [{device_address}] Complete Frame: {frame.hex().upper()}")
				    parse_bms_frame(frame, dname)
				    # You can parse the frame further here
				#logging.info("%s received %r", name_or_address, data)
			try:
				await client.start_notify(notify_uuid, callback)
				parsed = False
				for i in range(2):
					if parsed == False:
						await client.write_gatt_char(notify_uuid, COMMAND, response=True)
						#print(f"? Sent command to {address}")
						await asyncio.sleep(1)
				#await client.write_gatt_char(notify_uuid, COMMAND, response=True)
				await asyncio.sleep(10.0)
				await client.stop_notify(notify_uuid)
			except:
				print("", end="")

		# The stack context manager exits here, triggering disconnection.

		logging.info("disconnected from %s", dname)

	except Exception:
		logging.exception("error with %s", dname)


async def main(
	by_address: bool,
	macos_use_bdaddr: bool,
	uuid: str,
	):
	while True:
		await get_devices()
		lock = asyncio.Lock()
		
		print(f"Found {len(found_names)} devices")
		await asyncio.gather(
			*(
				connect_to_device(lock, by_address, macos_use_bdaddr, address, found_names[idx], uuid, idx)
				for idx, address in enumerate(found_devices)
			)
		)

		print ("Loop " + datetime.now().strftime("%H:%M:%S"))

		fields = list(bledata[0].keys())
		new_dict = {
			f: {k+1: bledata[k][f] for k in bledata}   # inner dict
			for f in fields                                   # outer loop
		}


		for f, col in new_dict.items():
			mindat = 99999.0
			minid = 1
			maxdat = -99999.0
			maxid = 1
			av = 0.0
			chg_mos = []
			dchg_mos = []
			chg_mos.append("All On")
			dchg_mos.append("All On")
			# 1) flatten the values of the column to a simple list
			values = list(col.values())
			if f != "name":
				try:
					
					if f == "chg_mos" or f == "dchg_mos":
						for i, dat in sorted(col.items()):
							if f == "chg_mos":
								if dat != "On":
									chg_mos.append(f"{dat} - {new_dict['name'][i]}")
							elif f == "dchg_mos":
								if dat != "On":
									dchg_mos.append(f"{dat} - {new_dict['name'][i]}")
					elif f != "temp":
						for i, dat in sorted(col.items()):
							if mindat > col[i]:
								mindat = col[i]
								minid = i
							if maxdat < col[i]:
								maxdat = col[i]
								maxid = i
					elif f == "temp":
						av = 0.0
						i = 0
						for i, dat in sorted(col.items()):
							for t in dat:
								av = av + t
							#Find min value
							if mindat > col[i][0]:
								mindat = col[i][0]
								minid = i
							if mindat > col[i][1]:
								mindat = col[i][1]
								minid = i
							#Find max value
							if maxdat < col[i][0]:
								maxdat = col[i][0]
								maxid = i
							if maxdat < col[i][1]:
								maxdat = col[i][1]
								maxid = i
						av = round(av / (i * 2), 2)

					# 2) calculate max, min, avg of that list
					if f != "chg_mos" and f != "dchg_mos":
						if av == 0.0:
							av = round(sum(values)/len(values), 2)
						mx, mn = maxdat, mindat
						# 3) put everything into a single nice string
						if f == "temp" and av > mx:
							print(col)
						print(f"{f}  max:{mx} - {new_dict['name'][maxid]}  min:{mn} - {new_dict['name'][minid]}  avg:{av}")#  : {col}")
					elif f == "dchg_mos":
						print(f"{f}  dchg_mos:{dchg_mos}")
					elif f == "chg_mos":
						print(f"{f}  chg_mos:{chg_mos}")
				except Exception as e:
					print (f"Exception {e}")

		blerestart()
		time.sleep(1)

async def get_devices():
	global found_devices, found_names
	found_devices = []
	found_names = []
	tout = 10
	logging.info("Scanning for %s s...", tout)
	#print(f"Scanning for 5sâ€¦")
	try:
		devices = await BleakScanner.discover(timeout=tout)
		for d in devices:
			if "BLE16ZNUB" in d.name:
				found_devices.append(str(d.address).replace("\r", ""))
				found_names.append(str(d.name).replace("\r", ""))
	except:
		print("")


def blerestart():
	if platform.system() == "Linux":
		s=os.system("sudo systemctl restart bluetooth")
		logging.info(f"restart bluetooth  %s ...", s)
	elif platform.system() == "Windows":
		s=os.system("net stop Bluetooth && net start Bluetooth")
		logging.info(f"restart bluetooth  %s ...", s)
	time.sleep(3)
	#return

if __name__ == "__main__":
	try: 
		blerestart()
		log_level = logging.INFO
		logging.basicConfig(
			level=log_level,
			format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
		)

		asyncio.run(
			main(
				True, False, "0000ffe1-0000-1000-8000-00805f9b34fb",
			)
		)
	except Exception as e:
		print(e)
		
